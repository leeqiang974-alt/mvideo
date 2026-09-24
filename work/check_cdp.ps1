$p = Get-Process chromex -ErrorAction SilentlyContinue
if ($p) { Write-Host ("chromex running: " + $p.Count + " procs") } else { Write-Host "chromex NOT running" }
$c = Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue
if ($c) { Write-Host "9222 LISTENING" } else { Write-Host "9222 NOT listening" }
try { (Invoke-WebRequest "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 4).StatusCode } catch { Write-Host "http err: $($_.Exception.Message)" }
