; Inno Setup script for Survey-to-KML.
; Build with:  ISCC installer.iss
; (produces installer_output\Survey-to-KML-Setup.exe)
;
; Prerequisite: dist\Survey-to-KML.exe must already exist — build it first
; with:  pyinstaller survey_to_kml.spec
;
; #define AppVersion is passed in from version.py by the build script
; (see BUILD.md); it defaults below so the script also works stand-alone.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{DCA72727-30A1-47C0-8780-D18CE6E6B1FB}
AppName=Survey-to-KML
AppVersion={#AppVersion}
AppPublisher=Nedson Suren
AppUpdatesURL=https://github.com/nedsonsuren/suren_survey_kml/releases
DefaultDirName={autopf}\Survey-to-KML
DefaultGroupName=Survey-to-KML
UninstallDisplayIcon={app}\Survey-to-KML.exe
OutputDir=installer_output
OutputBaseFilename=Survey-to-KML-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\Survey-to-KML.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Survey-to-KML"; Filename: "{app}\Survey-to-KML.exe"
Name: "{group}\Uninstall Survey-to-KML"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Survey-to-KML"; Filename: "{app}\Survey-to-KML.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Survey-to-KML.exe"; Description: "Launch Survey-to-KML now"; Flags: nowait postinstall skipifsilent
