; PrivateCopy Windows installer (Inno Setup 6). Build with installer/win/build_exe.ps1,
; which produces ..\..\dist\PrivateCopy\ first.
#define AppVersion "0.1.0"

[Setup]
AppId={{6E7A2C1B-3F4D-4B8E-9A61-5C2D7E8F9A10}
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
CloseApplications=yes
SetupIconFile=..\..\assets\privatecopy.ico
UninstallDisplayIcon={app}\PrivateCopy.exe
WizardImageFile=..\..\assets\wizard-image.bmp
WizardSmallImageFile=..\..\assets\wizard-small.bmp

[Tasks]
Name: "autostart"; Description: "Start PrivateCopy when I sign in"; GroupDescription: "Startup:"
Name: "intercept"; Description: "Redact every copy automatically (can be toggled from the tray)"; GroupDescription: "Behavior:"
Name: "llm"; Description: "Enable the optional local LLM pass (downloads about 400 MB on first start; slower)"; GroupDescription: "Behavior:"; Flags: unchecked

[Files]
Source: "..\..\dist\PrivateCopy\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\PrivateCopy"; Filename: "{app}\PrivateCopy.exe"
Name: "{group}\Uninstall PrivateCopy"; Filename: "{uninstallexe}"
Name: "{userstartup}\PrivateCopy"; Filename: "{app}\PrivateCopy.exe"; Tasks: autostart

[Run]
Filename: "{app}\PrivateCopy.exe"; Description: "Start PrivateCopy now"; Flags: postinstall nowait skipifsilent

[Code]
function BoolJson(B: Boolean): String;
begin
  if B then Result := 'true' else Result := 'false';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  CfgDir, Cfg: String;
begin
  if CurStep = ssPostInstall then begin
    { Same location the app reads: %USERPROFILE%\.privatecopy\config.json. Never overwrite on upgrade. }
    CfgDir := ExpandConstant('{%USERPROFILE}') + '\.privatecopy';
    Cfg := CfgDir + '\config.json';
    if not FileExists(Cfg) then begin
      ForceDirectories(CfgDir);
      SaveStringToFile(Cfg, '{"intercept_enabled": ' + BoolJson(WizardIsTaskSelected('intercept')) +
        ', "llm_enabled": ' + BoolJson(WizardIsTaskSelected('llm')) + '}', False);
    end;
  end;
end;
