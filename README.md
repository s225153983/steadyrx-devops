# SteadyRx DevOps pipeline

SteadyRx is an early warning service for medicine-related falls in older adults. A wearable sends daily gait summaries. When a medicine starts or a dose changes, the service compares walking in the 14 days before and after the change, classifies the medicine list against a falls-risk rules library, and places an explainable alert in the pharmacist risk queue.

This repository holds the SteadyRx API and the Jenkins pipeline that builds, tests, analyses, secures, deploys, releases and monitors it (SIT753 task 7.3HD).

## Features

| Area | Endpoints |
| --- | --- |
| Authentication (JWT, PBKDF2 passwords, roles) | `POST /api/v1/auth/login` |
| Patients | `GET/POST /api/v1/patients`, `GET /api/v1/patients/{id}` |
| Medicines with falls-risk classification | `GET/POST /api/v1/patients/{id}/medicines` |
| Gait readings and explainable insight | `POST /api/v1/patients/{id}/gait`, `GET /api/v1/patients/{id}/insight` |
| Pharmacist risk queue | `GET /api/v1/alerts`, `POST /api/v1/alerts/{id}/review` |
| Operations | `/health/live`, `/health/ready`, `/version`, `/metrics`, `/docs` |

Demo accounts (fictional): `daniel` / `Pharmacist!2026` (pharmacist) and `priya` / `Carer!2026` (carer).

## Technology

Python 3.12, FastAPI, SQLite, PyJWT, Prometheus client, pytest, Docker, Docker Compose, Jenkins, SonarCloud, flake8, pylint, radon, xenon, Bandit, pip-audit, Trivy, Prometheus, Alertmanager and Grafana.

## Pipeline

| Stage | What happens | Tools |
| --- | --- | --- |
| Build | Version `1.0.<build>-<sha>`, multi-stage Docker build, push to the local artefact registry | Docker, registry:2 |
| Test | Unit and integration tests, JUnit results, coverage gate of 90% | pytest, pytest-cov |
| Code Quality | Style, lint score, complexity gates, SonarCloud quality gate | flake8, pylint, radon, xenon, SonarCloud |
| Security | SAST, dependency CVEs, container CVEs, secrets and Dockerfile misconfiguration | Bandit, pip-audit, Trivy |
| Deploy | Compose deploy to staging, health check, automatic rollback, smoke tests | Docker Compose, PowerShell |
| Release | Promote the same image to `v1.0.<build>` and `stable`, deploy to production, smoke tests, Git tag, release notes | Docker registry, Docker Compose |
| Monitoring | Prometheus, Alertmanager, Grafana and the team alert channel, target and rule checks, incident drill | Prometheus, Alertmanager, Grafana |

## Run it locally

```bash
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest --cov
uvicorn app.main:app --reload                    # http://localhost:8000/docs
```

## Set up the pipeline in Jenkins

1. Install Docker Desktop and make sure `docker version` works for the account that runs Jenkins.
2. In Jenkins add a Secret text credential with the ID `SONAR_TOKEN` that holds a SonarCloud token.
3. Create a Pipeline job, choose "Pipeline script from SCM", Git, `https://github.com/s225153983/steadyrx-devops.git`, branch `*/main`, script path `Jenkinsfile`.
4. Click Build Now. After the run, open:
   * API docs http://localhost:8000/docs (production) and http://localhost:8001/docs (staging)
   * Grafana http://localhost:3000/d/steadyrx
   * Prometheus alerts http://localhost:9090/alerts
   * Team alert channel http://localhost:9095/

Optional. Add a Username with password credential with the ID `github-push` (a GitHub token with repo scope) so the Release stage also pushes the `v1.0.<build>` Git tag.

## Repository layout

```
app/                 FastAPI application
tests/unit           rules, gait engine, security, configuration
tests/integration    full API through the FastAPI test client
tests/smoke          post-deployment checks against staging and production
ci/                  PowerShell and shell scripts called by the Jenkinsfile
deploy/              Compose file and staging/production configuration
monitoring/          Prometheus, Alertmanager, Grafana and alert receiver
Jenkinsfile          the pipeline
```
