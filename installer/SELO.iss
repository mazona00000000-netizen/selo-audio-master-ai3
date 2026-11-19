[Setup]
AppId={{8D56F6D3-9F8B-4D56-9A4A-9E4A3D20A611}
AppName=SELO AUDIO MASTER AI
AppVersion=1.0.0
AppPublisher=SELO
DefaultDirName={autopf}\SELO AUDIO MASTER AI
DefaultGroupName=SELO AUDIO MASTER AI
OutputDir=..\dist-installer
OutputBaseFilename=SELO-AUDIO-MASTER-AI-Setup
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SELO AUDIO MASTER AI.exe

[Files]
Source: "..\dist\SELO AUDIO MASTER AI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SELO AUDIO MASTER AI"; Filename: "{app}\SELO AUDIO MASTER AI.exe"
Name: "{autodesktop}\SELO AUDIO MASTER AI"; Filename: "{app}\SELO AUDIO MASTER AI.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\SELO AUDIO MASTER AI.exe"; Description: "Launch SELO AUDIO MASTER AI"; Flags: postinstall nowait skipifsilent
