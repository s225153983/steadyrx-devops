"""Patients, medicines, gait readings and the pharmacist risk queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import current_user, get_service, require_pharmacist
from app.schemas import (Alert, GaitBatch, Medicine, MedicineIn, Patient,
                         PatientIn, ReviewRequest)
from app.services import NotFoundError, SteadyRxService

router = APIRouter(prefix="/api/v1", tags=["clinical"])


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/patients", response_model=list[Patient])
def list_patients(user: dict = Depends(require_pharmacist),
                  service: SteadyRxService = Depends(get_service)):
    return service.list_patients(user["sub"])


@router.post("/patients", response_model=Patient,
             status_code=status.HTTP_201_CREATED)
def create_patient(body: PatientIn, user: dict = Depends(require_pharmacist),
                   service: SteadyRxService = Depends(get_service)):
    return service.create_patient(body.name, body.age, body.consent_share,
                                  user["sub"])


@router.get("/patients/{patient_id}", response_model=Patient)
def get_patient(patient_id: int, _: dict = Depends(current_user),
                service: SteadyRxService = Depends(get_service)):
    try:
        return service.get_patient(patient_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/patients/{patient_id}/medicines", response_model=list[Medicine])
def list_medicines(patient_id: int, _: dict = Depends(current_user),
                   service: SteadyRxService = Depends(get_service)):
    try:
        return service.list_medicines(patient_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/patients/{patient_id}/medicines", response_model=Medicine,
             status_code=status.HTTP_201_CREATED)
def add_medicine(patient_id: int, body: MedicineIn,
                 user: dict = Depends(require_pharmacist),
                 service: SteadyRxService = Depends(get_service)):
    try:
        return service.add_medicine(patient_id, body.name, body.dose,
                                    body.start_date, user["sub"])
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/patients/{patient_id}/gait", status_code=status.HTTP_202_ACCEPTED)
def add_gait(patient_id: int, body: GaitBatch,
             _: dict = Depends(current_user),
             service: SteadyRxService = Depends(get_service)):
    try:
        stored = service.add_readings(
            patient_id, [r.model_dump() for r in body.readings])
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return {"stored": stored}


@router.get("/patients/{patient_id}/insight")
def insight(patient_id: int, _: dict = Depends(current_user),
            service: SteadyRxService = Depends(get_service)):
    try:
        return service.insight(patient_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/alerts", response_model=list[Alert])
def risk_queue(status_filter: str | None = "OPEN",
               _: dict = Depends(require_pharmacist),
               service: SteadyRxService = Depends(get_service)):
    return service.list_alerts(status_filter)


@router.post("/alerts/{alert_id}/review", response_model=Alert)
def review(alert_id: int, body: ReviewRequest,
           user: dict = Depends(require_pharmacist),
           service: SteadyRxService = Depends(get_service)):
    try:
        return service.review_alert(alert_id, body.outcome, user["sub"])
    except NotFoundError as exc:
        raise _not_found(exc) from exc
