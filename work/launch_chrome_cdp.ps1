$chrome = "C:\Users\Administrator\AppData\Local\Google\Chrome\Bin\chromex.exe"
$udd = "C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"
# kill hard
& taskkill /F /IM chromex.exe 2>$null | Out-Null
Start-Sleep -Seconds 4
$left = (Get-Process chromex -ErrorAction SilentlyContinue)
if ($left) { $left | Stop-Process -Force; Start-Sleep 3 }
Start-Process $chrome -ArgumentList @(
  "--remote-debugging-port=9222",
  "--user-data-dir=$udd",
  "--no-first-run",
  "--no-default-browser-check",
  "--restore-last-session=false",
  "https://seller.mvideo.ru/mpa/products/import"
)
$ok = $false
for ($i=0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 1
  try {
    $r = Invoke-WebRequest "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch { }
}
Write-Host ("CDP_OK=" + $ok + " after " + $i + "s")
