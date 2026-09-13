#Requires -Version 5.1
<# Thin launcher used by the Explorer verb: sends file text to the loopback service. #>
param([string]$File)
$text = Get-Content -Raw -LiteralPath $File
$body = @{ text = $text } | ConvertTo-Json
try {
  $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:48173/' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 60
  Set-Clipboard -Value $resp.redacted
  Write-Host "PrivateCopy: redacted $($resp.count) item(s) -> clipboard."
} catch {
  Write-Error "PrivateCopy daemon not running. Launch PrivateCopy first. $_"
  exit 1
}
