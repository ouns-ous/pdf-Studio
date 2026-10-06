#define AppName "PDF Studio"
#define AppVersion "1.2.0"

[Setup]
AppId={{17B925AE-7305-4919-9D65-F3B446E2EAAF}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PDF Studio
DefaultDirName={localappdata}\Programs\PDF Studio
DefaultGroupName=PDF Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=dist
OutputBaseFilename=PDF-Studio-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\PDF-Studio.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\PDF-Studio.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\PDF Studio"; Filename: "{app}\PDF-Studio.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\PDF Studio"; Filename: "{app}\PDF-Studio.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\PDF-Studio.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
