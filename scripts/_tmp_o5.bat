@echo off
powershell -NoProfile -Command "$lines=[IO.File]::ReadAllLines('C:\MvideoERP\.env',[Text.Encoding]::UTF8); $i=0; foreach($l in $lines){ if($l -match '^OZON_'){ Write-Output ($i.ToString()+'| '+$l.Substring(0,[Math]::Min(18,$l.Length))+' [len='+$l.Length.ToString()+']') }; $i++ }"
