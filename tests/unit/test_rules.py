"""Unit tests for the falls-risk medicine rules library."""

import pytest

from app.rules import classify_medicine, medication_burden


@pytest.mark.parametrize("name, drug_class", [
    ("Oxycodone 5 mg", "opioid"),
    ("TEMAZEPAM 10mg", "benzodiazepine"),
    ("  furosemide   40 mg", "diuretic"),
    ("Quetiapine", "antipsychotic"),
    ("Zolpidem 10 mg", "z-drug"),
])
def test_falls_risk_medicines_are_flagged(name, drug_class):
    result = classify_medicine(name)
    assert result.falls_risk is True
    assert result.drug_class == drug_class
    assert result.weight > 0


@pytest.mark.parametrize("name", ["Atorvastatin 20 mg", "Paracetamol", "Metformin"])
def test_other_medicines_are_not_flagged(name):
    result = classify_medicine(name)
    assert result.falls_risk is False
    assert result.drug_class is None


def test_burden_counts_each_class_once():
    single = medication_burden(["Temazepam 10 mg"])
    double = medication_burden(["Temazepam 10 mg", "Diazepam 5 mg"])
    assert single == double == 0.30


def test_burden_is_capped_at_one():
    names = ["Temazepam", "Oxycodone", "Quetiapine", "Sertraline",
             "Pregabalin", "Furosemide", "Prazosin"]
    assert medication_burden(names) == 1.0


def test_empty_list_has_no_burden():
    assert medication_burden([]) == 0.0
