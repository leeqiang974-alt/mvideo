Get-CimInstance Win32_Process -Filter "Name='chromex.exe'" | Select-Object ProcessId, ExecutablePath, CommandLine | Format-List
Write-Host "---ALL chromex-like---"
Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'chromex*' } | Select-Object ProcessId, Name, ExecutablePath | Format-Table -AutoSize -Wrap
