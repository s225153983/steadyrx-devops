# Sends a pipeline event to the team alert channel. Used when a build fails
# so the team hears about broken builds as well as production incidents.
param([string]$Status = 'FAILED', [string]$Summary = '', [string]$Severity = 'critical')
. "$PSScriptRoot\common.ps1"
$body = @{
    alertname = 'JenkinsPipeline' + $Status
    status = $(if ($Status -eq 'FAILED') { 'firing' } else { 'info' })
    severity = $Severity
    team = 'steadyrx'
    summary = $Summary
    description = "$env:JOB_NAME build $env:BUILD_NUMBER - $env:BUILD_URL"
}
try { Invoke-Json 'http://localhost:9095/alert' -Method POST -Body $body | Out-Null; Write-Host 'Team notified' }
catch { Write-Host 'Alert channel not reachable yet, notification skipped' }
