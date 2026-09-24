@echo off
powershell -NoProfile -Command "$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8077/health' -TimeoutSec 20; Write-Output ('ok=' + $r.ok + ' version=' + $r.version + ' omni_ok=' + $r.omni_ok + ' tables=' + $r.table_count)"
