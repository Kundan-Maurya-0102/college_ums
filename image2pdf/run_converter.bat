@echo off
echo ========================================================
echo   Setting up things for your PDF Converter... Wait :)
echo ========================================================

pip install Pillow >nul 2>&1
if %errorlevel% neq 0 (
    echo Pillow library already installed ya fir install ho rahi hai...
) else (
    echo Done installing requirement.
)

echo Starting your python program...
python image_to_pdf.py
pause
