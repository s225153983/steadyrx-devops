"""Before and after gait comparison engine.

When a medicine starts or its dose changes, SteadyRx compares the daily gait
summaries from the 14 days before the change with the days after it. The
engine returns a screening score between 0 and 1 and a plain-language list of
the factors behind that score, so the pharmacist can see why an alert fired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean

BASELINE_DAYS = 14
MIN_BASELINE_DAYS = 5
MIN_AFTER_DAYS = 3


@dataclass(frozen=True)
class DailyGait:
    """One day of summarised wearable data."""

    day: date
    cadence_spm: float          # steps per minute while walking
    step_variability_pct: float  # coefficient of variation of step time
    steps: int
    night_walks: int = 0


@dataclass
class GaitAssessment:
    """Result of one before and after comparison."""

    enough_data: bool
    cadence_change_pct: float = 0.0
    variability_change_pct: float = 0.0
    steps_change_pct: float = 0.0
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


def _pct_change(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return round((after - before) / before * 100, 1)


def _summary(window: list[DailyGait]) -> dict[str, float]:
    """Average the gait measures across one window of days."""
    return {"cadence": mean(r.cadence_spm for r in window),
            "variability": mean(r.step_variability_pct for r in window),
            "steps": mean(r.steps for r in window),
            "night_walks": sum(r.night_walks for r in window)}


def split_windows(readings: list[DailyGait], change_day: date
                  ) -> tuple[list[DailyGait], list[DailyGait]]:
    """Split readings into the baseline window and the after window."""
    start = change_day - timedelta(days=BASELINE_DAYS)
    before = [r for r in readings if start <= r.day < change_day]
    after = [r for r in readings if r.day >= change_day]
    return before, after


def assess(readings: list[DailyGait], change_day: date,
           medication_burden: float = 0.0, age: int | None = None
           ) -> GaitAssessment:
    """Compare gait before and after a medicine change.

    The score blends four signals. A drop in cadence and a rise in step
    variability are the strongest gait markers of falls risk. The medicine
    burden from the rules library and an age over 75 add context.
    """
    before, after = split_windows(readings, change_day)
    if len(before) < MIN_BASELINE_DAYS or len(after) < MIN_AFTER_DAYS:
        return GaitAssessment(enough_data=False,
                              reasons=["Not enough wear time to compare yet"])

    base, now = _summary(before), _summary(after)
    cadence = _pct_change(base["cadence"], now["cadence"])
    variability = _pct_change(base["variability"], now["variability"])
    steps = _pct_change(base["steps"], now["steps"])
    result = GaitAssessment(enough_data=True, cadence_change_pct=cadence,
                            variability_change_pct=variability,
                            steps_change_pct=steps)
    night_rise = now["night_walks"] > base["night_walks"]
    signals = (_gait_signals(cadence, variability, steps, night_rise)
               + _context_signals(medication_burden, age))
    result.reasons = [reason for _, reason in signals]
    score = sum(points for points, _ in signals)

    result.score = round(min(score, 1.0), 2)
    return result


def _gait_signals(cadence: float, variability: float, steps: float,
                  night_rise: bool) -> list[tuple[float, str]]:
    """Score the change in walking. Each signal adds points and a reason."""
    signals = []
    if cadence <= -5:
        signals.append((min(0.35, abs(cadence) / 100 * 3),
                        f"Walking cadence down {abs(cadence)}%"))
    if variability >= 10:
        signals.append((min(0.30, variability / 100 * 1.5),
                        f"Step variability up {variability}%"))
    if steps <= -20:
        signals.append((0.10, f"Daily steps down {abs(steps)}%"))
    if night_rise:
        signals.append((0.05, "More walking at night"))
    return signals


def _context_signals(medication_burden: float, age: int | None
                     ) -> list[tuple[float, str]]:
    """Score the clinical context around the gait change."""
    signals = []
    if medication_burden > 0:
        signals.append((0.25 * medication_burden,
                        f"Falls-risk medicine burden {medication_burden:.2f}"))
    if age is not None and age >= 75:
        signals.append((0.05, f"Age {age}"))
    return signals


def risk_level(score: float, high: float = 0.6, medium: float = 0.3) -> str:
    """Map a score to the traffic light shown to carers."""
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"
