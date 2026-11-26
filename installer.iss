; 瓦罗兰特翻译助手 安装包脚本（Inno Setup 6）
; 编译：ISCC.exe installer.iss

#define AppName "瓦罗兰特翻译助手"
#define AppNameEn "ValorantDanmaku"
#define AppVer "1.0"
#define AppExe "ValorantDanmaku.exe"

[Setup]
AppId={{8E4C1B27-6B3A-4F55-9C2E-2D7E8E1A5C10}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppNameEn}
DefaultGroupName={#AppName}
OutputDir=dist_installer
OutputBaseFilename={#AppName}-Setup-{#AppVer}
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
; 允许用户自选安装位置（含 C:\Program Files 之外的任意盘）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableDirPage=no
DisableProgramGroupPage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableWelcomePage=no
; 中文提示（向导本身是英文，但按钮/说明保持简短）

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "build\dist\ValorantDanmaku\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\cache"
