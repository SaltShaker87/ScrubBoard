; Scrubboard Windows installer (Inno Setup 6.3+). Build with installer/win/build_exe.ps1,
; which first produces ..\..\dist\Scrubboard\ and ..\build\text\win\ (installer/render_texts.py).
; All wording lives in scrubboard/texts.py; edit it there, not here.
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{3B8F1D52-7C6A-4E0B-9F2D-5A1C8E4B7D63}
AppName=Scrubboard
AppVersion={#AppVersion}
AppPublisher=Scrubboard contributors
AppComments=Removes patient identifiers from copied text before you paste it. Runs only on this computer.
DefaultDirName={autopf}\Scrubboard
DefaultGroupName=Scrubboard
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Scrubboard-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
; Offer to close a running Scrubboard automatically before upgrading or removing it.
CloseApplications=force
SetupIconFile=..\..\assets\scrubboard.ico
UninstallDisplayIcon={app}\Scrubboard.exe
UninstallDisplayName=Scrubboard
WizardImageFile=..\..\assets\wizard-image.bmp
WizardSmallImageFile=..\..\assets\wizard-small.bmp
LicenseFile=..\build\text\win\disclaimer.txt
InfoBeforeFile=..\build\text\win\howto.txt

#include "..\build\text\win\messages.iss"

[Tasks]
Name: "desktopicon"; Description: "Put a Scrubboard shortcut on my desktop"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start Scrubboard by itself when I sign in to Windows (recommended)"; GroupDescription: "Shortcuts:"
Name: "nohistory"; Description: "Turn off Windows clipboard history (recommended). Otherwise Windows keeps its own copy of everything you copy, including the original text before Scrubboard cleans it. You can turn it back on in Settings > System > Clipboard."; GroupDescription: "Privacy:"

[Files]
Source: "..\..\dist\Scrubboard\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Scrubboard"; Filename: "{app}\Scrubboard.exe"; Comment: "Clean patient details out of copied text"
Name: "{autodesktop}\Scrubboard"; Filename: "{app}\Scrubboard.exe"; Tasks: desktopicon; Comment: "Clean patient details out of copied text"
Name: "{userstartup}\Scrubboard"; Filename: "{app}\Scrubboard.exe"; Tasks: autostart

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Clipboard"; ValueType: dword; ValueName: "EnableClipboardHistory"; ValueData: 0; Tasks: nohistory

[Run]
Filename: "{app}\Scrubboard.exe"; Description: "Start Scrubboard now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM Scrubboard.exe /F"; Flags: runhidden; RunOnceId: "StopScrubboard"
