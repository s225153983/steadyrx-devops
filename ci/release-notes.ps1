# Writes release notes and a release manifest for the promoted version.
param([Parameter(Mandatory)][string]$Version, [Parameter(Mandatory)][string]$ImageTag,
      [string]$Registry = 'localhost:5000')
. "$PSScriptRoot\common.ps1"

$reports = Join-Path $RepoRoot 'reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
# HEAD~1 rather than HEAD^ because ^ is an escape character in cmd.
$lastTag = (& git describe --tags --abbrev=0 HEAD~1 2>$null | Out-String).Trim()
if ($lastTag) { $range = "$lastTag..HEAD" } else { $range = 'HEAD' }
$commits = (& git log $range --pretty=format:'- %h %s (%an)' -n 20 2>$null | Out-String).Trim()
$digest = Get-CmdOutput "docker inspect --format ""{{index .RepoDigests 0}}"" $Registry/steadyrx-api:v$Version"

$notes = @"
# SteadyRx API release v$Version

* Image: $Registry/steadyrx-api:v$Version (also tagged stable)
* Built from: $ImageTag
* Digest: $digest
* Jenkins build: $env:BUILD_URL
* Promoted from staging after unit, integration, quality gate, security and staging smoke tests passed.

## Changes since $(if ($lastTag) { $lastTag } else { 'the first release' })
$commits
"@
Set-Content -Path (Join-Path $reports 'release-notes.md') -Value $notes
[ordered]@{ version = $Version; image = "$Registry/steadyrx-api:v$Version"; source_tag = $ImageTag;
            digest = $digest; released_at = (Get-Date).ToString('s'); environment = 'production' } |
    ConvertTo-Json | Set-Content (Join-Path $reports 'release-manifest.json')
Write-Host $notes
