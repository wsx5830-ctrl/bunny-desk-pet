@echo off
cd /d "%~dp0"
title Push bunny-desk-pet to GitHub

set "LOG=%~dp0push-log.txt"
echo ==== push started %DATE% %TIME% ==== > "%LOG%"
echo git version: >> "%LOG%"
git --version >> "%LOG%" 2>&1

echo.
echo ============================================================
echo   Push bunny-desk-pet to GitHub  (user: wsx5830-ctrl)
echo ============================================================
echo.
echo   Repo must already exist as an EMPTY repo:
echo     https://github.com/wsx5830-ctrl/bunny-desk-pet
echo.

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo [info] remote not found, adding now
  git remote add origin https://github.com/wsx5830-ctrl/bunny-desk-pet.git >> "%LOG%" 2>&1
)

echo [info] remote = 
git remote -v
echo.

echo ----------------------------------------
echo  Pushing now.
echo  A browser window may pop up asking you
echo  to sign in to GitHub. Please sign in
echo  and authorize, then come back here.
echo ----------------------------------------
echo.

git push -u origin main --tags > "%LOG%.tmp" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%.tmp" >> "%LOG%"
del "%LOG%.tmp" >nul 2>&1

echo ---------------- output ----------------
type "%LOG%" | findstr /v "==== push started"
echo ----------------------------------------
echo.

if "%RC%"=="0" (
  echo [OK] Push finished successfully.
  echo.
  echo   Repo:  https://github.com/wsx5830-ctrl/bunny-desk-pet
  echo   Live:  https://bunny-desk-pet.app.workbuddy.host/
) else (
  echo [FAILED] git push returned exit code %RC%
  echo.
  echo Common causes:
  echo   1. The repo was not created on GitHub yet
  echo   2. Not signed in / authorization cancelled
  echo   3. Network or proxy blocked github.com
  echo.
  echo Full log saved to: %LOG%
)

echo.
echo Press any key to close this window...
pause >nul
