"""Integration tests that drive the full API through HTTP."""

from datetime import date, timedelta


def test_health_and_version(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] is True
    assert client.get("/version").json()["environment"] == "test"


def test_metrics_endpoint_exposes_custom_metrics(client):
    client.get("/health/live")
    body = client.get("/metrics").text
    assert "steadyrx_http_requests_total" in body
    assert "steadyrx_open_alerts" in body


def test_login_rejects_bad_password(client):
    res = client.post("/api/v1/auth/login",
                      json={"username": "daniel", "password": "nope"})
    assert res.status_code == 401


def test_protected_routes_need_a_token(client):
    assert client.get("/api/v1/alerts").status_code == 401
    bad = {"Authorization": "Bearer not.a.token"}
    assert client.get("/api/v1/alerts", headers=bad).status_code == 401


def test_carer_cannot_see_pharmacist_queue(client, carer):
    assert client.get("/api/v1/alerts", headers=carer).status_code == 403


def test_seeded_risk_queue_shows_margaret_high(client, pharmacist):
    alerts = client.get("/api/v1/alerts", headers=pharmacist).json()
    assert alerts[0]["patient_name"] == "Margaret Collins"
    assert alerts[0]["risk"] == "HIGH"
    assert alerts[0]["medicine"] == "Oxycodone 5 mg"


def test_end_to_end_medicine_change_raises_alert(client, pharmacist):
    patient = client.post("/api/v1/patients", headers=pharmacist,
                          json={"name": "Ron P", "age": 84}).json()
    pid = patient["id"]
    change = date.today() - timedelta(days=7)
    readings = []
    for offset in range(-14, 7):
        after = offset >= 0
        readings.append({
            "day": (change + timedelta(days=offset)).isoformat(),
            "cadence_spm": 88 if after else 102,
            "step_variability_pct": 7.0 if after else 5.0,
            "steps": 2000 if after else 3500})
    res = client.post(f"/api/v1/patients/{pid}/gait", headers=pharmacist,
                      json={"readings": readings})
    assert res.status_code == 202
    assert res.json()["stored"] == 21

    med = client.post(f"/api/v1/patients/{pid}/medicines", headers=pharmacist,
                      json={"name": "Quetiapine 25 mg", "dose": "25 mg nocte",
                            "start_date": change.isoformat()})
    assert med.status_code == 201
    assert med.json()["falls_risk"] is True
    assert med.json()["drug_class"] == "antipsychotic"

    insight = client.get(f"/api/v1/patients/{pid}/insight",
                         headers=pharmacist).json()
    assert insight["risk"] == "HIGH"
    assert insight["linked_medicine"] == "Quetiapine 25 mg"

    queue = client.get("/api/v1/alerts", headers=pharmacist).json()
    alert = next(a for a in queue if a["patient_id"] == pid)
    reviewed = client.post(f"/api/v1/alerts/{alert['id']}/review",
                           headers=pharmacist,
                           json={"outcome": "Called patient, dose reduced"})
    assert reviewed.json()["status"] == "REVIEWED"
    assert reviewed.json()["reviewed_by"] == "daniel"
    queue = client.get("/api/v1/alerts", headers=pharmacist).json()
    assert all(a["id"] != alert["id"] for a in queue)


def test_stable_patient_gets_no_alert(client, pharmacist):
    queue = client.get("/api/v1/alerts", headers=pharmacist).json()
    assert all(a["patient_name"] != "Joan K" for a in queue)
    insight = client.get("/api/v1/patients/2/insight", headers=pharmacist).json()
    assert insight["risk"] == "LOW"


def test_patient_without_medicines(client, pharmacist):
    pid = client.post("/api/v1/patients", headers=pharmacist,
                      json={"name": "New Person", "age": 70}).json()["id"]
    insight = client.get(f"/api/v1/patients/{pid}/insight",
                         headers=pharmacist).json()
    assert insight["risk"] == "LOW"
    assert client.get(f"/api/v1/patients/{pid}/medicines",
                      headers=pharmacist).json() == []


def test_missing_records_return_404(client, pharmacist):
    assert client.get("/api/v1/patients/999", headers=pharmacist).status_code == 404
    assert client.get("/api/v1/patients/999/medicines",
                      headers=pharmacist).status_code == 404
    assert client.get("/api/v1/patients/999/insight",
                      headers=pharmacist).status_code == 404
    res = client.post("/api/v1/patients/999/medicines", headers=pharmacist,
                      json={"name": "Oxycodone", "dose": "5 mg",
                            "start_date": "2026-09-01"})
    assert res.status_code == 404
    res = client.post("/api/v1/patients/999/gait", headers=pharmacist,
                      json={"readings": [{"day": "2026-09-01", "cadence_spm": 90,
                                          "step_variability_pct": 5, "steps": 10}]})
    assert res.status_code == 404
    res = client.post("/api/v1/alerts/999/review", headers=pharmacist,
                      json={"outcome": "none"})
    assert res.status_code == 404


def test_validation_rejects_bad_input(client, pharmacist):
    res = client.post("/api/v1/patients", headers=pharmacist,
                      json={"name": "", "age": 5})
    assert res.status_code == 422


def test_patient_list_is_scoped_to_pharmacist(client, pharmacist):
    names = [p["name"] for p in client.get("/api/v1/patients",
                                           headers=pharmacist).json()]
    assert "Margaret Collins" in names
    one = client.get("/api/v1/patients/1", headers=pharmacist).json()
    assert one["age"] == 78


def test_reviewed_filter_and_all_alerts(client, pharmacist):
    all_alerts = client.get("/api/v1/alerts?status_filter=",
                            headers=pharmacist).json()
    assert len(all_alerts) >= 1
