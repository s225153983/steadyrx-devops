"""Falls-risk increasing drug (FRID) rules library.

The classes follow the STOPPFall screening tool, which lists the medicine
classes most strongly linked to falls in older adults. The weights are
illustrative screening weights, not clinical doses.
"""

from __future__ import annotations

from dataclasses import dataclass

# Medicine class -> (weight, example generic names)
FRID_CLASSES: dict[str, tuple[float, tuple[str, ...]]] = {
    "benzodiazepine": (0.30, ("temazepam", "diazepam", "oxazepam", "alprazolam",
                              "lorazepam", "nitrazepam", "clonazepam")),
    "z-drug": (0.25, ("zolpidem", "zopiclone")),
    "opioid": (0.30, ("oxycodone", "morphine", "tramadol", "tapentadol",
                      "codeine", "hydromorphone", "buprenorphine", "fentanyl")),
    "antipsychotic": (0.25, ("quetiapine", "olanzapine", "risperidone",
                             "haloperidol", "aripiprazole")),
    "antidepressant": (0.20, ("sertraline", "citalopram", "escitalopram",
                              "mirtazapine", "amitriptyline", "venlafaxine")),
    "antiepileptic": (0.15, ("pregabalin", "gabapentin", "carbamazepine",
                             "sodium valproate", "levetiracetam")),
    "diuretic": (0.15, ("furosemide", "frusemide", "hydrochlorothiazide",
                        "indapamide", "spironolactone")),
    "alpha-blocker": (0.15, ("prazosin", "tamsulosin", "terazosin")),
    "antihypertensive": (0.10, ("amlodipine", "perindopril", "ramipril",
                                "irbesartan", "candesartan", "metoprolol")),
    "sedating-antihistamine": (0.15, ("promethazine", "doxylamine",
                                      "diphenhydramine")),
}


@dataclass(frozen=True)
class RuleResult:
    """Outcome of checking one medicine against the rules library."""

    falls_risk: bool
    drug_class: str | None
    weight: float


def classify_medicine(name: str) -> RuleResult:
    """Return the falls-risk class for a medicine name.

    Matching is case-insensitive and ignores strength, so "Oxycodone 5 mg"
    matches the opioid class.
    """
    cleaned = " ".join(name.lower().split())
    for drug_class, (weight, members) in FRID_CLASSES.items():
        for member in members:
            if cleaned.startswith(member):
                return RuleResult(True, drug_class, weight)
    return RuleResult(False, None, 0.0)


def medication_burden(names: list[str]) -> float:
    """Sum the FRID weights for a medicine list, capped at 1.0.

    Two drugs from the same class only count once because the second adds
    little extra risk compared with a new class.
    """
    seen: dict[str, float] = {}
    for name in names:
        result = classify_medicine(name)
        if result.falls_risk and result.drug_class not in seen:
            seen[result.drug_class] = result.weight
    return min(1.0, round(sum(seen.values()), 3))
