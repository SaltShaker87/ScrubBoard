#Requires -Version 5.1
# Windows build: Scrubboard.exe (+ bundled privacy detector and llama-server), then the
# Inno Setup installer dist\Scrubboard-Setup.exe.
#   powershell -ExecutionPolicy Bypass -File installer/win/build_exe.ps1
# Code signing (optional): set SIGNTOOL_ARGS, e.g.
#   '/fd sha256 /tr http://timestamp.digicert.com /td sha256 /a'
# Unsigned builds work but show "Windows protected your PC" (More info -> Run anyway).
$ErrorActionPreference = 'Stop'
python -m pip install -e . pyinstaller
python installer/fetch_llama.py
python installer/fetch_models.py
python installer/render_texts.py
pyinstaller --noconfirm --clean installer/scrubboard.spec
$version = python -c "import scrubboard; print(scrubboard.__version__)"
if ($env:SIGNTOOL_ARGS) {
  signtool sign $env:SIGNTOOL_ARGS.Split(' ') dist\Scrubboard\Scrubboard.exe
}
if (-not (Get-Command iscc -ErrorAction SilentlyContinue)) {
  $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
  if (-not (Test-Path $iscc)) { throw 'Inno Setup 6 not found (choco install innosetup).' }
} else { $iscc = 'iscc' }
& $iscc "/DAppVersion=$version" installer/win/innosetup.iss
Move-Item -Force installer\win\Output\Scrubboard-Setup.exe dist\Scrubboard-Setup.exe
if ($env:SIGNTOOL_ARGS) {
  signtool sign $env:SIGNTOOL_ARGS.Split(' ') dist\Scrubboard-Setup.exe
}
Write-Host "OK: dist\Scrubboard-Setup.exe"
