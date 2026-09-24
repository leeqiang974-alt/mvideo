@echo off
powershell -NoProfile -Command "$lines=[IO.File]::ReadAllLines('C:\MvideoERP\.env',[Text.Encoding]::UTF8); for($i=0;$i -lt $lines.Count;$i++){ if($lines[$i] -match '^OZON_(CLIENT_ID|API_KEY)='){ Write-Output ($i.ToString()+'| '+$lines[$i].Substring(0,[Math]::Min(40,$lines[$i].Length))+' [len='+$lines[$i].Length.ToString()+']') } }"
