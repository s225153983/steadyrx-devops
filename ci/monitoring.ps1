# Starts or refreshes the monitoring stack and proves it is watching production.
. "$PSScriptRoot\common.ps1"

$compose = Join-Path $RepoRoot 'monitoring\docker-compose.yml'
Invoke-Cmd "docker compose -p steadyrx-monitoring -f `"$compose`" up -d --build --remove-orphans" | Out-Null

# Wait for each component to answer.
$checks = @{
    'Prometheus'     = 'http://localhost:9090/-/ready'
    'Alertmanager'   = 'http://localhost:9093/-/ready'
    'Grafana'        = 'http://localhost:3000/api/health'
    'Alert receiver' = 'http://localhost:9095/health'
}
foreach ($name in $checks.Keys) {
    $ok = $false
    for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
        try { Invoke-WebRequest -Uri $checks[$name] -UseBasicParsing -TimeoutSec 3 | Out-Null; $ok = $true }
        catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ok) { throw "$name did not become ready" }
    Write-Host "$name is ready"
}

# Reload so rule or target changes in this commit take effect immediately.
Invoke-WebRequest -Uri 'http://localhost:9090/-/reload' -Method POST -UseBasicParsing | Out-Null
Invoke-WebRequest -Uri 'http://localhost:9093/-/reload' -Method POST -UseBasicParsing | Out-Null

$prodUp = $false
for ($i = 0; $i -lt 20 -and -not $prodUp; $i++) {
    $targets = Invoke-Json 'http://localhost:9090/api/v1/targets'
    $prod = $targets.data.activeTargets | Where-Object { $_.labels.job -eq 'steadyrx-production' }
    if ($prod -and $prod.health -eq 'up') { $prodUp = $true } else { Start-Sleep -Seconds 3 }
}
if (-not $prodUp) { throw 'Prometheus cannot scrape the production API' }
Write-Host 'Prometheus is scraping steadyrx-production (health=up)'

$rules = Invoke-Json 'http://localhost:9090/api/v1/rules'
$ruleNames = @($rules.data.groups | ForEach-Object { $_.rules } | ForEach-Object { $_.name })
Write-Host "Alert rules loaded ($($ruleNames.Count)): $($ruleNames -join ', ')"
if ($ruleNames.Count -lt 5) { throw 'Expected at least five alert rules' }

$query = [uri]::EscapeDataString('sum(rate(steadyrx_http_requests_total{job="steadyrx-production"}[1m]))')
$rps = Invoke-Json "http://localhost:9090/api/v1/query?query=$query"
$summary = [ordered]@{
    checked_at = (Get-Date).ToString('s')
    production_target = 'up'
    alert_rules = $ruleNames
    production_request_rate = $rps.data.result
    grafana = 'http://localhost:3000/d/steadyrx'
    prometheus = 'http://localhost:9090/alerts'
    alert_channel = 'http://localhost:9095/'
}
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot 'reports') | Out-Null
$summary | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $RepoRoot 'reports\monitoring-summary.json')
Write-Host 'Monitoring stack verified. Dashboard: http://localhost:3000/d/steadyrx'
