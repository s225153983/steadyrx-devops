// SteadyRx DevOps pipeline (SIT753 7.3HD)
// Build -> Test -> Code Quality -> Security -> Deploy -> Release -> Monitoring
// Every stage works on the same versioned image, and each stage is a gate:
// if it fails, later stages do not run and the team is notified.

def dockerTest(String cmd) {
    // Runs a command inside the test image with the reports folder mounted.
    bat "docker run --rm -v \"%WORKSPACE%\\reports:/app/reports\" steadyrx-test:%IMAGE_TAG% ${cmd}"
}

pipeline {
    agent any

    parameters {
        booleanParam(name: 'SIMULATE_INCIDENT', defaultValue: true,
            description: 'Run the brute-force login incident drill against production after release')
        booleanParam(name: 'CHAOS_API_DOWN', defaultValue: false,
            description: 'Also stop the production API to prove the ApiDown alert and recovery')
    }

    environment {
        REGISTRY       = 'localhost:5000'
        IMAGE          = 'steadyrx-api'
        VERSION_PREFIX = '1.0'
        DOCKER_BUILDKIT = '1'
        // Docker Desktop CLI location, so the Jenkins service finds docker
        // even if it started before Docker Desktop was installed.
        PATH = "C:\\Program Files\\Docker\\Docker\\resources\\bin;${env.PATH}"
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '10'))
    }

    stages {
        stage('Build') {
            steps {
                script {
                    env.GIT_SHORT = bat(returnStdout: true, script: '@git rev-parse --short HEAD').trim()
                    env.VERSION = "${env.VERSION_PREFIX}.${env.BUILD_NUMBER}"
                    env.IMAGE_TAG = "${env.VERSION}-${env.GIT_SHORT}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} v${env.VERSION}"
                    currentBuild.description = "commit ${env.GIT_SHORT}, image ${env.IMAGE}:${env.IMAGE_TAG}"
                }
                echo "Building ${IMAGE}:${IMAGE_TAG} from commit ${GIT_SHORT}"
                bat 'if exist reports rmdir /s /q reports & mkdir reports'
                powershell '& .\\ci\\ensure-registry.ps1'
                bat 'docker build --target runtime --build-arg APP_VERSION=%VERSION% --build-arg BUILD_SHA=%GIT_SHORT% -t %REGISTRY%/%IMAGE%:%IMAGE_TAG% .'
                bat 'docker build --target test -t steadyrx-test:%IMAGE_TAG% .'
                bat 'docker push %REGISTRY%/%IMAGE%:%IMAGE_TAG%'
                bat 'docker image inspect %REGISTRY%/%IMAGE%:%IMAGE_TAG% --format "{{json .}}" > reports\\build-image.json'
                echo "Artefact stored in the registry as ${REGISTRY}/${IMAGE}:${IMAGE_TAG}"
            }
        }

        stage('Test') {
            steps {
                echo 'Unit and integration tests with pytest. The stage fails below 90% coverage.'
                dockerTest('pytest tests/unit tests/integration --junitxml=reports/junit.xml --cov --cov-report=xml:reports/coverage.xml --cov-report=term --cov-fail-under=90')
            }
            post {
                always { junit testResults: 'reports/junit.xml', allowEmptyResults: false }
            }
        }

        stage('Code Quality') {
            steps {
                echo 'Local gates: flake8, pylint >= 9.5, radon and xenon complexity limits.'
                dockerTest('bash ci/quality.sh')
                echo 'SonarCloud analysis. The build waits for the quality gate result.'
                withCredentials([string(credentialsId: 'SONAR_TOKEN', variable: 'SONAR_TOKEN')]) {
                    bat 'docker run --rm -e SONAR_TOKEN -v "%WORKSPACE%:/usr/src" sonarsource/sonar-scanner-cli:11.4 -Dsonar.projectVersion=%VERSION% -Dsonar.qualitygate.wait=true -Dsonar.qualitygate.timeout=300'
                }
            }
        }

        stage('Security') {
            failFast true
            parallel {
                stage('SAST and dependencies') {
                    steps {
                        echo 'Bandit scans the source. pip-audit checks pinned dependencies against the PyPI advisory database.'
                        dockerTest('bash ci/security.sh')
                    }
                }
                stage('Container image') {
                    steps {
                        echo 'Trivy 0.69.3 (a release that predates the March 2026 supply chain compromise) scans the runtime image.'
                        bat 'docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v steadyrx-trivy-cache:/root/.cache -v "%WORKSPACE%\\reports:/reports" aquasec/trivy:0.69.3 image --scanners vuln --format json --output /reports/trivy-image.json %REGISTRY%/%IMAGE%:%IMAGE_TAG%'
                        bat 'docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v steadyrx-trivy-cache:/root/.cache aquasec/trivy:0.69.3 image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 %REGISTRY%/%IMAGE%:%IMAGE_TAG%'
                    }
                }
                stage('Secrets and IaC') {
                    steps {
                        echo 'Trivy scans the repository for committed secrets and Dockerfile misconfiguration.'
                        bat 'docker run --rm -v steadyrx-trivy-cache:/root/.cache -v "%WORKSPACE%:/src" aquasec/trivy:0.69.3 fs --scanners secret,misconfig --skip-dirs /src/reports --format json --output /src/reports/trivy-repo.json /src'
                        bat 'docker run --rm -v steadyrx-trivy-cache:/root/.cache -v "%WORKSPACE%:/src" aquasec/trivy:0.69.3 fs --scanners secret,misconfig --skip-dirs /src/reports --severity HIGH,CRITICAL --exit-code 1 /src'
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                echo "Deploying ${IMAGE_TAG} to the staging environment with Docker Compose"
                powershell '& .\\ci\\deploy.ps1 -Environment staging -ImageTag $env:IMAGE_TAG -ExpectedVersion $env:VERSION'
                echo 'Post-deployment smoke tests against staging'
                bat 'docker run --rm -e BASE_URL=http://host.docker.internal:8001 -e EXPECTED_VERSION=%VERSION% -v "%WORKSPACE%\\reports:/app/reports" steadyrx-test:%IMAGE_TAG% pytest tests/smoke --junitxml=reports/smoke-staging.xml'
            }
            post {
                always { junit testResults: 'reports/smoke-staging.xml', allowEmptyResults: true }
            }
        }

        stage('Release') {
            steps {
                echo "Promoting ${IMAGE_TAG} to production as release v${VERSION}"
                bat 'docker tag %REGISTRY%/%IMAGE%:%IMAGE_TAG% %REGISTRY%/%IMAGE%:v%VERSION%'
                bat 'docker tag %REGISTRY%/%IMAGE%:%IMAGE_TAG% %REGISTRY%/%IMAGE%:stable'
                bat 'docker push %REGISTRY%/%IMAGE%:v%VERSION%'
                bat 'docker push %REGISTRY%/%IMAGE%:stable'
                powershell '& .\\ci\\deploy.ps1 -Environment production -ImageTag "v$env:VERSION" -ExpectedVersion $env:VERSION'
                bat 'docker run --rm -e BASE_URL=http://host.docker.internal:8000 -e EXPECTED_VERSION=%VERSION% -v "%WORKSPACE%\\reports:/app/reports" steadyrx-test:%IMAGE_TAG% pytest tests/smoke --junitxml=reports/smoke-production.xml'
                bat 'git tag -f -a v%VERSION% -m "SteadyRx release v%VERSION% (Jenkins build %BUILD_NUMBER%)"'
                powershell '& .\\ci\\release-notes.ps1 -Version $env:VERSION -ImageTag $env:IMAGE_TAG'
                script {
                    // Pushing the Git tag is optional. It runs only when a
                    // 'github-push' username and token credential exists.
                    try {
                        withCredentials([usernamePassword(credentialsId: 'github-push',
                                usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
                            bat 'git push https://%GH_USER%:%GH_TOKEN%@github.com/s225153983/steadyrx-devops.git v%VERSION%'
                        }
                    } catch (err) {
                        echo "Git tag v${env.VERSION} created locally. Remote push skipped: ${err.getMessage()}"
                    }
                }
            }
            post {
                always { junit testResults: 'reports/smoke-production.xml', allowEmptyResults: true }
            }
        }

        stage('Monitoring') {
            steps {
                echo 'Starting Prometheus, Alertmanager, Grafana and the team alert channel, then verifying production is monitored.'
                powershell '& .\\ci\\monitoring.ps1'
                script {
                    if (params.SIMULATE_INCIDENT == null || params.SIMULATE_INCIDENT) {
                        powershell '& .\\ci\\simulate-incident.ps1 -Scenario brute-force'
                    }
                    if (params.CHAOS_API_DOWN) {
                        powershell '& .\\ci\\simulate-incident.ps1 -Scenario api-down'
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true, fingerprint: true
        }
        success {
            echo "Release v${env.VERSION} is live. API http://localhost:8000/docs, Grafana http://localhost:3000/d/steadyrx, alerts http://localhost:9095/"
            powershell '& .\\ci\\notify.ps1 -Status SUCCEEDED -Severity info -Summary "Release v$env:VERSION deployed to production"'
        }
        failure {
            powershell '& .\\ci\\notify.ps1 -Status FAILED -Summary "Pipeline failed for $env:IMAGE_TAG"'
        }
        cleanup {
            bat 'docker image prune -f'
        }
    }
}
