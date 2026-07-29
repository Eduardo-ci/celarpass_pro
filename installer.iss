[Setup]
; Información de la Aplicación
AppName=CelarPass
AppVersion=1.0.4
AppPublisher=Eduardo
AppPublisherURL=https://github.com/Eduardo-ci/CelarPass_Pro
AppSupportURL=https://github.com/Eduardo-ci/CelarPass_Pro/issues
AppUpdatesURL=https://github.com/Eduardo-ci/CelarPass_Pro/releases

; Configuración por defecto de instalación
DefaultDirName={autopf}\CelarPass
DefaultGroupName=CelarPass

; Iconos e interfaz
SetupIconFile=resources\icons\cipherpass.ico
UninstallDisplayIcon={app}\celarpass.exe

; Configuración de salida
OutputDir=dist
OutputBaseFilename=CelarPass_Setup
Compression=lzma2
SolidCompression=yes

; Permisos (Privilegios mínimos si es posible, pero usualmente admin)
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.UninstallShortcut=Desinstalar CelarPass
english.UninstallShortcut=Uninstall CelarPass

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Archivo ejecutable principal
Source: "dist\celarpass.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Acceso directo en el menú de inicio
Name: "{group}\CelarPass"; Filename: "{app}\celarpass.exe"; IconFilename: "{app}\celarpass.exe"
; Acceso directo de desinstalación en el menú de inicio
Name: "{group}\{cm:UninstallShortcut}"; Filename: "{uninstallexe}"
; Acceso directo en el escritorio (opcional)
Name: "{autodesktop}\CelarPass"; Filename: "{app}\celarpass.exe"; Tasks: desktopicon

[Run]
; Casilla para ejecutar al finalizar
Filename: "{app}\celarpass.exe"; Description: "{cm:LaunchProgram,CelarPass}"; Flags: nowait postinstall skipifsilent
