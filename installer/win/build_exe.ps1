#Requires -Version 5.1
# Windows build: PrivateCopy.exe (+ bundled llama-server), then the Inno Setup installer.
#   powershell -ExecutionPolicy Bypass -File installer/win/build_exe.ps1
# Sign dist\PrivateCopy\PrivateCopy.exe and the installer with your code-signing
# certificate (signtool) before distributing; unsigned builds trigger SmartScreen.
$ErrorActionPreference = 'Stop'
python -m pip install -e . pyinstaller
python installer/fetch_llama.py
pyinstaller --noconfirm --clean installer/privatecopy.spec
if (Get-Command iscc -ErrorAction SilentlyContinue) {
  iscc installer/win/innosetup.iss
} else {
  Write-Host 'Inno Setup (iscc) not on PATH; skipped the installer. dist\PrivateCopy\ is ready.'
}
