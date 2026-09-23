# Deploys one image tag to staging or production with Docker Compose.
# The last healthy tag for each environment is recorded, so a failed health
# check rolls the environment back to the version that worked before.
param(
    [Parameter(Mandatory)][ValidateSet('staging', 'production')][string]$Environment,
    [Parameter(Mandatory)][string]$ImageTag,
    [string]$ExpectedVersion = '',
    [string]$Registry = 'localhost:5000'
)
. "$PSScriptRoot\common.ps1"

$envFile = Join-Path $RepoRoot "deploy\config\$Environment.env"
$compose = Join-Path $RepoRoot 'deploy\docker-compose.app.yml'
$config = Read-EnvFile $envFile
$port = $config['HOST_PORT']
$stateDir = Get-StateDir
$tagFile = Join-Path $stateDir "$Environment.tag"
$secretFile = Join-Path $stateDir "$Environment.jwt"
$historyFile = Join-Path $stateDir "$Environment-history.log"

# The JWT signing key is generated once per environment and kept outside the
# repository, so no secret is ever committed.
if (-not (Test-Path $secretFile)) {
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    Set-Content -Path $secretFile -Value ([Convert]::ToBase64String($bytes)) -NoNewline
    Write-Host "Generated a new JWT signing key for $Environment"
}
$previous = ''
if (Test-Path $tagFile) { $previous = (Get-Content $tagFile -Raw).Trim() }

function Start-Release([string]$Tag) {
    $env:IMAGE_TAG = $Tag
    $env:REGISTRY = $Registry
    $env:DEPLOY_ENV = $Environment
    $env:HOST_PORT = $port
    $env:JWT_SECRET = (Get-Content $secretFile -Raw).Trim()
    Invoke-Cmd "docker compose -p steadyrx-$Environment --env-file `"$envFile`" -f `"$compose`" pull --quiet" | Out-Null
    Invoke-Cmd "docker compose -p steadyrx-$Environment --env-file `"$envFile`" -f `"$compose`" up -d --remove-orphans" | Out-Null
}

Write-Host "Deploying $Registry/steadyrx-api:$ImageTag to $Environment (port $port). Previous: $(if ($previous) { $previous } else { 'none' })"
Start-Release $ImageTag

if (Wait-Healthy -BaseUrl "http://localhost:$port" -ExpectedVersion $ExpectedVersion) {
    Set-Content -Path $tagFile -Value $ImageTag -NoNewline
    Add-Content -Path $historyFile -Value "$(Get-Date -Format s) deployed $ImageTag"
    Write-Host "Deployment of $ImageTag to $Environment succeeded"
    exit 0
}

Write-Host "Health check failed for $ImageTag in $Environment"
Invoke-Cmd "docker logs --tail 50 steadyrx-$Environment" -AllowFail | Out-Null
if ($previous -and $previous -ne $ImageTag) {
    Write-Host "Rolling $Environment back to $previous"
    Start-Release $previous
    if (Wait-Healthy -BaseUrl "http://localhost:$port") {
        Add-Content -Path $historyFile -Value "$(Get-Date -Format s) rollback to $previous after $ImageTag failed"
        Write-Host "Rollback to $previous succeeded"
    }
}
exit 1
