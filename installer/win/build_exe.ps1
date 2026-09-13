#Requires -Version 5.1
# Windows: build the PrivateCopy EXE with the logo icon, then run Inno Setup.
#   pip install pillow pyinstaller; python scripts/make_icons.py
#   powershell -ExecutionPolicy Bypass -File installer/win/build_exe.ps1
#   iscc installer/win/innosetup.iss
$ErrorActionPreference = 'Stop'
$Icon = 'assets/privatecopy.ico'
$IconArgs = @()
if (Test-Path $Icon) { $IconArgs = @('--icon', $Icon) }
pyinstaller --noconfirm --clean --onedir --name PrivateCopy @IconArgs `
  --add-data 'assets/privatecopy-logo.png;assets' privatecopy/cli.py
