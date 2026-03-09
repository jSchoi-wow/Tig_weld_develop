@echo off
cd /d C:\Users\user\Desktop\TIG_weld_develop
git add .
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "auto commit %date% %time%"
    git push
    echo Push completed: %date% %time%
) else (
    echo No changes to commit.
)
