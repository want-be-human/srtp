@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo  Pushing srtp-main code to Gitee
echo ============================================
echo.

cd /d "C:\Users\chen\Desktop\计算机设计\srtp-main"

echo [1/4] Showing current remote...
git remote -v

echo.
echo [2/4] Adding all files to git...
git add -A

echo.
echo [3/4] Creating initial commit...
git commit -m "Initial commit: SRTP weld inspection teaching system"

echo.
echo [4/4] Ensuring branch is 'main' and pushing to Gitee...
git branch -M main
git push -u origin main

echo.
echo ============================================
echo  DONE! 
echo  View your repo at: https://gitee.com/shollorak/srtp-main
echo ============================================
pause