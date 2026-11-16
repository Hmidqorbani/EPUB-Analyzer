; EPUB Analyzer - Inno Setup script
; 1) Build the exe first:  pyinstaller ... gui.py   (creates dist\EPUBAnalyzer.exe)
; 2) Open this file in Inno Setup and press Build > Compile (or run: ISCC installer.iss)

#define MyAppName "EPUB Analyzer"
#define MyAppVersion "1.2.0"
#define MyAppExeName "EPUBAnalyzer.exe"

[Setup]
AppId={{6F3B2C1E-8A47-4D5B-9E0C-2B7A41D9C5F3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=EPUBAnalyzer-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Optional Persian UI (unofficial translation): download Farsi.isl from
; https://jrsoftware.org/files/istrans/ , put it next to this file and uncomment:
; Name: "farsi"; MessagesFile: "Farsi.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; WebView data (saved theme etc.) created by gui.py
Type: filesandordirs; Name: "{userappdata}\EPUBAnalyzer"
