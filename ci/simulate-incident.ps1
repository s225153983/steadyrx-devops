# Incident drill. Creates a real problem in production and proves the
# monitoring stack detects it and alerts the team, then records the time to
# detect. Two scenarios are available.
#   brute-force : 25 failed logins, expecting SteadyRxLoginFailureSpike
#   api-down    : stops the production container, expecting SteadyRxApiDown,
#                 then restarts it and waits for the resolved notification
param([ValidateSet('brute-force', 'api-down')][string]$Scenario = 'brute-force',
      [int]$TimeoutSeconds = 150)
. "$PSScriptRoot\common.ps1"

$prod = 'http://localhost:8000'
$receiver = 'http://localhost:9095/alerts'

function Wait-Alert([string]$Name, [string]$Status, [datetime]$Since) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $events = @(Invoke-Json $receiver)
        $hit = $events | Where-Object {
            $_.alertname -eq $Name -and $_.status -eq $Status -and
            ([datetime]::Parse($_.received_at).ToUniversalTime() -ge $Since)
        } | Select-Object -First 1
        if ($hit) { return $hit }
        Start-Sleep -Seconds 3
    }
    return $null
}

$start = (Get-Date).ToUniversalTime()
if ($Scenario -eq 'brute-force') {
    $alertName = 'SteadyRxLoginFailureSpike'
    Write-Host 'Simulating a password guessing attack with 25 failed logins'
    for ($i = 1; $i -le 25; $i++) {
        try { Invoke-Json "$prod/api/v1/auth/login" -Method POST -Body @{ username = 'daniel'; password = "guess$i" } | Out-Null }
        catch { }
    }
} else {
    $alertName = 'SteadyRxApiDown'
    Write-Host 'Simulating an outage by stopping the production container'
    Invoke-Cmd 'docker stop steadyrx-production' | Out-Null
}

$fired = Wait-Alert $alertName 'firing' $start
if (-not $fired) {
    if ($Scenario -eq 'api-down') { Invoke-Cmd 'docker start steadyrx-production' -AllowFail | Out-Null }
    throw "$alertName was not delivered to the team channel within $TimeoutSeconds seconds"
}
$ttd = [math]::Round(([datetime]::Parse($fired.received_at).ToUniversalTime() - $start).TotalSeconds, 1)
Write-Host "ALERT DELIVERED: $alertName ($($fired.severity)) in $ttd s - $($fired.summary)"

$result = [ordered]@{ scenario = $Scenario; alert = $alertName; time_to_detect_seconds = $ttd }
if ($Scenario -eq 'api-down') {
    $recover = (Get-Date).ToUniversalTime()
    Invoke-Cmd 'docker start steadyrx-production' | Out-Null
    if (-not (Wait-Healthy -BaseUrl $prod)) { throw 'Production did not recover after the drill' }
    $resolved = Wait-Alert $alertName 'resolved' $recover
    if ($resolved) {
        $result.time_to_resolve_seconds = [math]::Round(([datetime]::Parse($resolved.received_at).ToUniversalTime() - $recover).TotalSeconds, 1)
        Write-Host "RESOLVED notification received after $($result.time_to_resolve_seconds) s"
    }
}
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot 'reports') | Out-Null
$result | ConvertTo-Json | Set-Content (Join-Path $RepoRoot "reports\incident-$Scenario.json")
