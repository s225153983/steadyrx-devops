# Shared helpers for the Jenkins pipeline scripts (Windows PowerShell 5.1).
# Native commands run through cmd so Docker progress messages on stderr do
# not surface as PowerShell errors, and exit codes are checked explicitly.

$ErrorActionPreference = 'Continue'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Invoke-Cmd {
    param([Parameter(Mandatory)][string]$Command, [switch]$AllowFail)
    Write-Host "> $Command"
    cmd /c "$Command 2>&1" | ForEach-Object { Write-Host $_ }
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFail) {
        throw "Command failed with exit code ${code}: $Command"
    }
    return $code
}

function Get-CmdOutput {
    param([Parameter(Mandatory)][string]$Command)
    $out = cmd /c "$Command 2>nul"
    if ($null -eq $out) { return '' }
    return (($out | Out-String).Trim())
}

function Get-StateDir {
    $base = $env:JENKINS_HOME
    if (-not $base) { $base = Join-Path $RepoRoot '.state' }
    $dir = Join-Path $base 'steadyrx-state'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}

function Read-EnvFile {
    param([Parameter(Mandatory)][string]$Path)
    $values = @{}
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*([A-Z_]+)=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
    }
    return $values
}

function Invoke-Json {
    param([Parameter(Mandatory)][string]$Uri, [string]$Method = 'GET', $Body = $null)
    $params = @{ Uri = $Uri; Method = $Method; UseBasicParsing = $true; TimeoutSec = 5 }
    if ($null -ne $Body) {
        $params.Body = ($Body | ConvertTo-Json -Depth 5 -Compress)
        $params.ContentType = 'application/json'
    }
    return Invoke-RestMethod @params
}

function Wait-Healthy {
    param([Parameter(Mandatory)][string]$BaseUrl, [string]$ExpectedVersion = '',
          [int]$TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $ready = Invoke-Json "$BaseUrl/health/ready"
            $ver = Invoke-Json "$BaseUrl/version"
            if ($ready.database -and (-not $ExpectedVersion -or $ver.version -eq $ExpectedVersion)) {
                Write-Host "Healthy: $BaseUrl is serving version $($ver.version) in $($ver.environment)"
                return $true
            }
            Write-Host "Waiting: $BaseUrl reports version $($ver.version)"
        } catch {
            Write-Host "Waiting for $BaseUrl ..."
        }
        Start-Sleep -Seconds 3
    }
    return $false
}
