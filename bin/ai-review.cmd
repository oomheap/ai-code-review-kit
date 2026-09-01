@echo off
setlocal
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0ai-review.py" %*
) else (
  python "%~dp0ai-review.py" %*
)
exit /b %errorlevel%
