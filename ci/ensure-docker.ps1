# Prepares the Docker CLI for the Jenkins service account.
# Jenkins runs as a Windows service, so it does not inherit the Docker
# Desktop user settings. This script gives it a private Docker config that
# points at Docker Desktop's CLI plugins (compose and buildx) and checks that
# the engine answers before any stage relies on it.
. "$PSScriptRoot\common.ps1"

$configDir = $env:DOCKER_CONFIG
if (-not $configDir) { throw 'DOCKER_CONFIG is not set' }
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$pluginDir = Join-Path $env:DOCKER_DESKTOP 'resources\cli-plugins'
$config = @{ cliPluginsExtraDirs = @($pluginDir) } | ConvertTo-Json
Set-Content -Path (Join-Path $configDir 'config.json') -Value $config -Encoding ASCII

$ready = $false
for ($i = 0; $i -lt 20 -and -not $ready; $i++) {
    $v = Get-CmdOutput 'docker version --format "{{.Server.Version}}"'
    if ($v) { $ready = $true } else { Write-Host 'Waiting for the Docker engine...'; Start-Sleep -Seconds 3 }
}
if (-not $ready) { throw 'Docker engine is not reachable. Start Docker Desktop and rerun the build.' }
Invoke-Cmd 'docker version --format "Docker engine {{.Server.Version}} ({{.Server.Os}}/{{.Server.Arch}})"' | Out-Null
Invoke-Cmd 'docker compose version' | Out-Null
Invoke-Cmd 'docker buildx version' | Out-Null
