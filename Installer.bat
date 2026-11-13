@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
    if /i not "%~1"=="/auto" pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install mss pyautogui pillow numpy opencv-python pynput img2pdf pytesseract pypdf pyinstaller
if errorlevel 1 goto fail

echo Building executable...
python -m PyInstaller --onefile --windowed --clean --icon PageCapture.ico --add-data "fonts;fonts" --add-data "PageCapture.ico;." --name PageCapture page_capture.py
if errorlevel 1 goto fail

echo Creating shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe = Join-Path '%~dp0dist' 'PageCapture.exe'; $ico = Join-Path '%~dp0' 'PageCapture.ico'; $ws = New-Object -ComObject WScript.Shell; foreach ($dir in @([Environment]::GetFolderPath('Desktop'), '%~dp0')) { $s = $ws.CreateShortcut((Join-Path $dir 'Page Capture.lnk')); $s.TargetPath = $exe; $s.WorkingDirectory = (Split-Path $exe); $s.IconLocation = $ico; $s.Description = 'Page Capture - Becine Tools'; $s.Save() }"
if errorlevel 1 goto fail

echo.
echo Done: dist\PageCapture.exe
echo Shortcuts created on the Desktop and in this folder.
if /i not "%~1"=="/auto" pause
exit /b 0

:fail
echo Something went wrong. Check the messages above.
if /i not "%~1"=="/auto" pause
exit /b 1
