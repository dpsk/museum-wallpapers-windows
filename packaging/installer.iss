; Inno Setup 6 script: a per-user installer (no administrator prompt) for the
; PyInstaller folder. Built by packaging/build.py, which passes the defines.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\MuseumWallpapers"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef IconFile
  #define IconFile "build\icon.ico"
#endif
#define AppName "Museum Wallpapers"
#define AppExe "MuseumWallpapers.exe"
#define AppUserModelID "dpsk.MuseumWallpapers"

[Setup]
AppId={{46D0738B-BCDE-4609-9C32-0852D85831CA}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=dpsk
AppPublisherURL=https://github.com/dpsk/museum-wallpapers-windows
AppSupportURL=https://github.com/dpsk/museum-wallpapers-windows/issues
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
WizardStyle=modern
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename=MuseumWallpapers-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
en.Autostart=Start with Windows
ru.Autostart=Запускать вместе с Windows
en.Shortcuts=Shortcuts:
ru.Shortcuts=Ярлыки:
en.Launch=Start {#AppName} now
ru.Launch=Запустить {#AppName}

[Tasks]
Name: "autostart"; Description: "{cm:Autostart}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:Shortcuts}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; The app's "Start with Windows" menu item reads and writes this same value.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MuseumWallpapers"; ValueData: """{app}\{#AppExe}"" --background"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "MuseumWallpapers"; Flags: uninsdeletevalue dontcreatekey
; Name and icon on toast notifications.
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\{#AppUserModelID}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\{#AppUserModelID}"; ValueType: string; ValueName: "IconUri"; ValueData: "{app}\_internal\icon.ico"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "StopApp"

[UninstallDelete]
; Cache, state and settings. Saved paintings (in Pictures) stay.
Type: filesandordirs; Name: "{localappdata}\MuseumWallpapers"
Type: filesandordirs; Name: "{userappdata}\MuseumWallpapers"

[Code]
// An update replaces files the running app holds open: stop it first.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
