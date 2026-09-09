@echo off
pwsh -NoLogo -NoProfile -File "%~dp0tools\Build-Haks.ps1" %*
exit /b %ERRORLEVEL%
