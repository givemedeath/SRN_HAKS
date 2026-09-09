@echo off
pwsh -NoLogo -NoProfile -File "%~dp0tools\Test-Repository.ps1" %*
exit /b %ERRORLEVEL%
