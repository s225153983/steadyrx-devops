"""Request and response models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials sent to the login endpoint."""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Signed access token returned after login."""

    access_token: str
    token_type: str = "bearer"
    role: str


class PatientIn(BaseModel):
    """Fields needed to enrol a patient."""

    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=18, le=120)
    consent_share: bool = True


class Patient(PatientIn):
    """A stored patient record."""

    id: int
    pharmacist: str


class MedicineIn(BaseModel):
    """A new medicine or dose change."""

    name: str = Field(min_length=2, max_length=100)
    dose: str = Field(min_length=1, max_length=50)
    start_date: date


class Medicine(MedicineIn):
    """A stored medicine with its falls-risk class."""

    id: int
    patient_id: int
    falls_risk: bool
    drug_class: str | None = None


class GaitReadingIn(BaseModel):
    """One day of gait summary from the watch."""

    day: date
    cadence_spm: float = Field(gt=0, le=250)
    step_variability_pct: float = Field(ge=0, le=100)
    steps: int = Field(ge=0, le=100_000)
    night_walks: int = Field(default=0, ge=0, le=50)


class GaitBatch(BaseModel):
    """A batch of daily gait summaries."""

    readings: list[GaitReadingIn] = Field(min_length=1, max_length=366)


class Alert(BaseModel):
    """An entry in the pharmacist risk queue."""

    id: int
    patient_id: int
    patient_name: str
    medicine: str | None
    risk: str
    score: float
    reasons: list[str]
    status: str
    created_at: str
    reviewed_by: str | None = None


class ReviewRequest(BaseModel):
    """The pharmacist outcome when closing an alert."""

    outcome: str = Field(min_length=3, max_length=500)
