@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install mss pyautogui pillow numpy opencv-python pynput img2pdf pytesseract pypdf pyinstaller
if errorlevel 1 goto fail

echo Building executable...
python -m PyInstaller --onefile --windowed --clean --add-data "fonts;fonts" --name PageCapture page_capture.py
if errorlevel 1 goto fail

echo Creating shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe = Join-Path '%~dp0dist' 'PageCapture.exe'; $ws = New-Object -ComObject WScript.Shell; foreach ($dir in @([Environment]::GetFolderPath('Desktop'), '%~dp0')) { $s = $ws.CreateShortcut((Join-Path $dir 'Page Capture.lnk')); $s.TargetPath = $exe; $s.WorkingDirectory = (Split-Path $exe); $s.Description = 'Page Capture - Becine Tools'; $s.Save() }"
if errorlevel 1 goto fail

echo.
echo Done: dist\PageCapture.exe
echo Shortcuts created on the Desktop and in this folder.
pause
exit /b 0

:fail
echo Something went wrong. Check the messages above.
pause
exit /b 1
