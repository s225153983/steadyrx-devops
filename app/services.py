"""Business logic that links medicines, gait data and alerts."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from app import gait, rules
from app.config import Settings
from app.database import Database
from app.metrics import ALERTS_CREATED, OPEN_ALERTS


class NotFoundError(Exception):
    """Raised when a requested record does not exist."""


class SteadyRxService:
    """Application service used by the API routers."""

    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # Patients -------------------------------------------------------------
    def list_patients(self, pharmacist: str | None = None) -> list[dict]:
        if pharmacist:
            return self.db.query(
                "SELECT * FROM patients WHERE pharmacist=? ORDER BY id",
                (pharmacist,))
        return self.db.query("SELECT * FROM patients ORDER BY id")

    def get_patient(self, patient_id: int) -> dict:
        rows = self.db.query("SELECT * FROM patients WHERE id=?", (patient_id,))
        if not rows:
            raise NotFoundError(f"Patient {patient_id} not found")
        return rows[0]

    def create_patient(self, name: str, age: int, consent: bool,
                       pharmacist: str) -> dict:
        cur = self.db.execute(
            "INSERT INTO patients (name, age, pharmacist, consent_share) "
            "VALUES (?,?,?,?)", (name, age, pharmacist, int(consent)))
        self.db.audit(pharmacist, "patient.create", {"id": cur.lastrowid})
        return self.get_patient(cur.lastrowid)

    # Medicines ------------------------------------------------------------
    def list_medicines(self, patient_id: int) -> list[dict]:
        self.get_patient(patient_id)
        return self.db.query(
            "SELECT * FROM medicines WHERE patient_id=? ORDER BY start_date",
            (patient_id,))

    def add_medicine(self, patient_id: int, name: str, dose: str,
                     start_date: date, actor: str) -> dict:
        """Record a medicine change and run the gait comparison for it."""
        self.get_patient(patient_id)
        rule = rules.classify_medicine(name)
        cur = self.db.execute(
            "INSERT INTO medicines (patient_id, name, dose, start_date, "
            "falls_risk, drug_class) VALUES (?,?,?,?,?,?)",
            (patient_id, name, dose, start_date.isoformat(),
             int(rule.falls_risk), rule.drug_class))
        self.db.audit(actor, "medicine.add",
                      {"patient": patient_id, "medicine": name})
        self.evaluate(patient_id)
        return self.db.query("SELECT * FROM medicines WHERE id=?",
                             (cur.lastrowid,))[0]

    # Gait -----------------------------------------------------------------
    def add_readings(self, patient_id: int, readings: list[dict]) -> int:
        self.get_patient(patient_id)
        for r in readings:
            self.db.execute(
                "INSERT OR REPLACE INTO gait_readings VALUES (?,?,?,?,?,?)",
                (patient_id, r["day"].isoformat(), r["cadence_spm"],
                 r["step_variability_pct"], r["steps"],
                 r.get("night_walks", 0)))
        self.evaluate(patient_id)
        return len(readings)

    def _readings(self, patient_id: int) -> list[gait.DailyGait]:
        rows = self.db.query(
            "SELECT * FROM gait_readings WHERE patient_id=? ORDER BY day",
            (patient_id,))
        return [gait.DailyGait(date.fromisoformat(r["day"]), r["cadence_spm"],
                               r["step_variability_pct"], r["steps"],
                               r["night_walks"]) for r in rows]

    def insight(self, patient_id: int) -> dict:
        """Return the latest assessment without creating an alert."""
        patient = self.get_patient(patient_id)
        meds = self.list_medicines(patient_id)
        if not meds:
            return {"patient_id": patient_id, "risk": "LOW", "score": 0.0,
                    "reasons": ["No medicines recorded"]}
        latest = meds[-1]
        result = self._assess(patient, meds, latest)
        return {"patient_id": patient_id,
                "linked_medicine": latest["name"],
                "change_date": latest["start_date"],
                "risk": self._level(result.score) if result.enough_data
                else "UNKNOWN",
                "score": result.score,
                "cadence_change_pct": result.cadence_change_pct,
                "variability_change_pct": result.variability_change_pct,
                "steps_change_pct": result.steps_change_pct,
                "reasons": result.reasons}

    def _assess(self, patient: dict, meds: list[dict], latest: dict):
        burden = rules.medication_burden([m["name"] for m in meds])
        return gait.assess(self._readings(patient["id"]),
                           date.fromisoformat(latest["start_date"]),
                           medication_burden=burden, age=patient["age"])

    def _level(self, score: float) -> str:
        return gait.risk_level(score, self.settings.risk_threshold_high,
                               self.settings.risk_threshold_medium)

    # Alerts ---------------------------------------------------------------
    def evaluate(self, patient_id: int) -> dict | None:
        """Raise or refresh an alert for the most recent medicine change."""
        patient = self.get_patient(patient_id)
        meds = self.list_medicines(patient_id)
        if not meds:
            return None
        latest = meds[-1]
        result = self._assess(patient, meds, latest)
        if not result.enough_data:
            return None
        level = self._level(result.score)
        if level == "LOW":
            return None
        existing = self.db.query(
            "SELECT id FROM alerts WHERE patient_id=? AND medicine_id=? "
            "AND status='OPEN'", (patient_id, latest["id"]))
        reasons = json.dumps(result.reasons)
        if existing:
            self.db.execute(
                "UPDATE alerts SET risk=?, score=?, reasons=? WHERE id=?",
                (level, result.score, reasons, existing[0]["id"]))
            alert_id = existing[0]["id"]
        else:
            cur = self.db.execute(
                "INSERT INTO alerts (patient_id, medicine_id, risk, score, "
                "reasons, created_at) VALUES (?,?,?,?,?,?)",
                (patient_id, latest["id"], level, result.score, reasons,
                 datetime.now(timezone.utc).isoformat()))
            alert_id = cur.lastrowid
            ALERTS_CREATED.labels(risk=level).inc()
        self.refresh_gauges()
        return self.get_alert(alert_id)

    def list_alerts(self, status: str | None = "OPEN") -> list[dict]:
        sql = ("SELECT a.*, p.name AS patient_name, m.name AS medicine "
               "FROM alerts a JOIN patients p ON p.id=a.patient_id "
               "LEFT JOIN medicines m ON m.id=a.medicine_id")
        params: tuple = ()
        if status:
            sql += " WHERE a.status=?"
            params = (status,)
        sql += " ORDER BY a.score DESC, a.id"
        return [self._alert_row(r) for r in self.db.query(sql, params)]

    def get_alert(self, alert_id: int) -> dict:
        rows = self.db.query(
            "SELECT a.*, p.name AS patient_name, m.name AS medicine "
            "FROM alerts a JOIN patients p ON p.id=a.patient_id "
            "LEFT JOIN medicines m ON m.id=a.medicine_id WHERE a.id=?",
            (alert_id,))
        if not rows:
            raise NotFoundError(f"Alert {alert_id} not found")
        return self._alert_row(rows[0])

    def review_alert(self, alert_id: int, outcome: str, actor: str) -> dict:
        self.get_alert(alert_id)
        self.db.execute(
            "UPDATE alerts SET status='REVIEWED', reviewed_by=? WHERE id=?",
            (actor, alert_id))
        self.db.audit(actor, "alert.review",
                      {"alert": alert_id, "outcome": outcome})
        self.refresh_gauges()
        return self.get_alert(alert_id)

    def refresh_gauges(self) -> None:
        counts = {"HIGH": 0, "MEDIUM": 0}
        for row in self.db.query(
                "SELECT risk, COUNT(*) AS n FROM alerts WHERE status='OPEN' "
                "GROUP BY risk"):
            counts[row["risk"]] = row["n"]
        for risk, n in counts.items():
            OPEN_ALERTS.labels(risk=risk).set(n)

    @staticmethod
    def _alert_row(row: dict) -> dict:
        row = dict(row)
        row["reasons"] = json.loads(row["reasons"])
        return row
