# Starts the local Docker registry that stores every build artefact.
. "$PSScriptRoot\common.ps1"

$state = Get-CmdOutput 'docker inspect -f "{{.State.Running}}" steadyrx-registry'
if ($state -eq 'true') {
    Write-Host 'Artefact registry steadyrx-registry is already running on localhost:5000'
} elseif ($state -eq 'false') {
    Invoke-Cmd 'docker start steadyrx-registry' | Out-Null
} else {
    Invoke-Cmd 'docker run -d --restart=always -p 5000:5000 --name steadyrx-registry -v steadyrx-registry:/var/lib/registry registry:2.8.3' | Out-Null
}
