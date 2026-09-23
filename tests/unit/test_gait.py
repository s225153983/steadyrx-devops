"""Unit tests for the before and after gait engine."""

from datetime import date, timedelta

import pytest

from app.gait import DailyGait, assess, risk_level, split_windows

CHANGE = date(2026, 9, 1)


def make_readings(before_cadence, after_cadence, before_var=5.0, after_var=5.0,
                  before_steps=3000, after_steps=3000, days_after=7,
                  after_night=0):
    readings = []
    for offset in range(-14, days_after):
        after = offset >= 0
        readings.append(DailyGait(
            CHANGE + timedelta(days=offset),
            after_cadence if after else before_cadence,
            after_var if after else before_var,
            after_steps if after else before_steps,
            after_night if after else 0))
    return readings


def test_split_windows_uses_fourteen_day_baseline():
    readings = make_readings(100, 100)
    extra = DailyGait(CHANGE - timedelta(days=30), 100, 5, 3000)
    before, after = split_windows([extra] + readings, CHANGE)
    assert len(before) == 14
    assert len(after) == 7


def test_stable_walking_gives_low_score():
    result = assess(make_readings(100, 99), CHANGE)
    assert result.enough_data
    assert result.score == 0.0
    assert risk_level(result.score) == "LOW"


def test_declining_walking_gives_high_score_with_reasons():
    readings = make_readings(104, 90, before_var=5, after_var=6.5,
                             before_steps=4000, after_steps=2800, after_night=3)
    result = assess(readings, CHANGE, medication_burden=0.75, age=80)
    assert result.cadence_change_pct == pytest.approx(-13.5)
    assert result.variability_change_pct == pytest.approx(30.0)
    assert result.score >= 0.6
    assert risk_level(result.score) == "HIGH"
    joined = " ".join(result.reasons)
    for word in ("cadence", "variability", "steps", "night", "burden", "Age"):
        assert word in joined


def test_not_enough_data_after_change():
    result = assess(make_readings(100, 80, days_after=2), CHANGE)
    assert result.enough_data is False
    assert result.score == 0.0


def test_score_is_capped_at_one():
    readings = make_readings(120, 40, before_var=2, after_var=20,
                             before_steps=8000, after_steps=500, after_night=9)
    result = assess(readings, CHANGE, medication_burden=1.0, age=90)
    assert result.score == 1.0


@pytest.mark.parametrize("score, level", [
    (0.0, "LOW"), (0.29, "LOW"), (0.3, "MEDIUM"), (0.59, "MEDIUM"),
    (0.6, "HIGH"), (1.0, "HIGH")])
def test_risk_level_thresholds(score, level):
    assert risk_level(score) == level


def test_zero_baseline_does_not_divide_by_zero():
    readings = make_readings(100, 100, before_steps=0, after_steps=100)
    assert assess(readings, CHANGE).steps_change_pct == 0.0
