param([string]$Username = '__local_probe__')
$ErrorActionPreference = 'Stop'
$settings = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'application.properties') | ConvertFrom-StringData
$port = $settings['server.port']
$report = [ordered]@{
    checked_at = (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')
    plugin_url = "http://127.0.0.1:$port"
    publish_allowed_ips = $settings['server.ips']
    platform_config_present = (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'config/platformConfig.json'))
    plugin_responding = $false
    account_requires_ukey = $null
    assistant_responding = $false
    device_detected = $false
    errors = @()
}
try {
    $account = [Uri]::EscapeDataString($Username)
    $report.account_requires_ukey = Invoke-RestMethod -Uri "$($report.plugin_url)/verifyUser?username=$account" -TimeoutSec 5
    $report.plugin_responding = $true
} catch {
    $report.errors += 'Plugin request failed: ' + $_.Exception.Message
}
try {
    $device = Invoke-RestMethod -Uri 'http://127.0.0.1:38080/sys/getDevInfo' -Method Post -ContentType 'application/x-www-form-urlencoded' -TimeoutSec 5
    $report.assistant_responding = $true
    $report.device_detected = $device.code -eq 200 -and -not [string]::IsNullOrWhiteSpace($device.SerialNumber)
} catch {
    $report.errors += 'UKey assistant request failed: ' + $_.Exception.Message
}
$report | ConvertTo-Json -Depth 3
if (-not $report.plugin_responding -or -not $report.assistant_responding -or -not $report.device_detected) { exit 1 }
if (-not $report.platform_config_present) { exit 2 }
