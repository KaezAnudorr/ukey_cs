param([Parameter(Mandatory=$true)][string]$Role, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'manage.py') $Role @Rest
exit $LASTEXITCODE
