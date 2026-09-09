@echo off
pwsh -NoLogo -NoProfile -File "%~dp0tools\Build-Tlk.ps1" %*
exit /b %ERRORLEVEL%
