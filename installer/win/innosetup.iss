; PrivateCopy Windows installer (Inno Setup 6).
; Build order: python scripts/make_icons.py -> installer/win/build_exe.ps1 -> iscc installer/win/innosetup.iss
; PyInstaller output expected in ..\..\dist\PrivateCopy\.
#define AppVersion "0.1.0"

[Setup]
AppId={{3A1F7E5A-9C2B-4E6A-9F1A-PRIVATECOPY01}
AppName=PrivateCopy
AppVersion={#AppVersion}
AppPublisher=PrivateCopy contributors
DefaultDirName={autopf}\PrivateCopy
DefaultGroupName=PrivateCopy
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=PrivateCopy-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\assets\privatecopy.ico
UninstallDisplayIcon={app}\privatecopy.exe
WizardImageFile=..\..\assets\wizard-image.bmp
WizardSmallImageFile=..\..\assets\wizard-small.bmp

[Files]
Source: "..\..\dist\PrivateCopy\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PrivateCopy"; Filename: "{app}\privatecopy.exe"; Parameters: "daemon"
Name: "{userstartup}\PrivateCopy"; Filename: "{app}\privatecopy.exe"; Parameters: "daemon"

[Registry]
; Optional Explorer file verb (HKCU, no admin)
Root: HKCU; Subkey: "Software\Classes\*\shell\PrivateCopy"; ValueType: string; ValueData: "PrivateCopy (redact file text)"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\PrivateCopy\command"; ValueType: string; ValueData: """{app}\privatecopy.exe"" run-once --file ""%1"""

[Code]
var
  HotkeyPage: TWizardPage;
  HotkeyEdit: TEdit;

function BoolToStr(B: Boolean): String;
begin
  if B then Result := 'True' else Result := 'False';
end;

procedure InitializeWizard;
begin
  HotkeyPage := CreateCustomPage(wpSelectTasks, 'Keyboard shortcut',
    'PrivateCopy trigger (default Ctrl+Shift+C). Keep it or type your own, e.g. Ctrl+Shift+P.');
  HotkeyEdit := TEdit.Create(WizardForm);
  HotkeyEdit.Parent := HotkeyPage.Surface;
  HotkeyEdit.Width := 300;
  HotkeyEdit.Text := 'ctrl+shift+c';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  CfgDir, Cfg: String;
begin
  if CurStep = ssPostInstall then begin
    CfgDir := ExpandConstant('{userappdata}\..\.privatecopy');
    ForceDirectories(CfgDir);
    Cfg := CfgDir + '\hotkey.txt';
    SaveStringToFile(Cfg, HotkeyEdit.Text, False);
  end;
end;
