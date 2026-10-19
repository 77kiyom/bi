@echo off
chcp 65001 >nul
cd /d "C:\Users\wujie15\WorkBuddy AI\2026-10-15-10-13-19\bi_dashboard\gh_repo"
set HTTP_PROXY=http://127.0.0.1:7897
set HTTPS_PROXY=http://127.0.0.1:7897
set GIT="C:\Users\wujie15\AppData\Local\Programs\WorkBuddyAI\resources\vendor\PortableGit\cmd\git.exe"
echo ==== 1/3 sync with remote ====
%GIT% fetch origin main
%GIT% reset --soft origin/main
%GIT% add -A
%GIT% -c user.name="WorkBuddy" -c user.email="workbuddy@users.noreply.github.com" commit -m "update dashboard" 2>nul
echo ==== 2/3 push ====
%GIT% push origin main
echo.
echo ==== 3/3 done, exit code = %errorlevel% ====
pause
