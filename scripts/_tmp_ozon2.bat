@echo off
powershell -NoProfile -Command "$p='C:\Users\Administrator\Desktop\api\ozonapi.txt'; $lines=[IO.File]::ReadAllLines($p,[Text.Encoding]::GetEncoding(936)); Write-Output ('total: '+$lines.Count); for($i=0;$i -lt $lines.Count;$i++){ $s=$lines[$i].TrimEnd(); if($s.Trim().Length -gt 0){ Write-Output ($i.ToString()+'| '+$s) } }"
