Get-Process | Where-Object { $_.ProcessName -match 'chrome|msedge|chromium|firefox|brave|opera' } | Select-Object -Unique ProcessName | Format-Table -AutoSize
Write-Host "---SEARCH chrome.exe---"
$paths = @(
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "C:\Users\Administrator\AppData\Local\Chromium\Application\chrome.exe",
  "D:\Google\Chrome\Application\chrome.exe",
  "C:\Users\AdministratorR\AppData\Local\Google\Chrome\Application\chrome.exe"
)
foreach ($p in $paths) { if (Test-Path $p) { Write-Host "FOUND: $p" } }
Write-Host "---WHERE---"
Get-Command chrome.exe -ErrorAction SilentlyContinue | Select-Object Source
Get-Command msedge.exe -ErrorAction SilentlyContinue | Select-Object Source
