@echo off
chcp 65001 >nul
cd /d "C:\Users\wujie15\WorkBuddy AI\2026-10-15-10-13-19\bi_dashboard\gh_repo"
set HTTP_PROXY=http://127.0.0.1:7897
set HTTPS_PROXY=http://127.0.0.1:7897
set GIT="C:\Users\wujie15\AppData\Local\Programs\WorkBuddyAI\resources\vendor\PortableGit\cmd\git.exe"
echo ==== pushing to GitHub via proxy 127.0.0.1:7897 ====
%GIT% -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push -u origin main --force
echo.
echo ==== done, exit code = %errorlevel% ====
pause
