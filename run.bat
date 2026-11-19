@echo off
REM تشغيل استوديو الراوي (ويندوز)
cd /d "%~dp0"
python -m app.server %*
pause
