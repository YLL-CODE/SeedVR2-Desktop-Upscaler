#ifndef SourceRoot
  #error SourceRoot is required
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

#define AppName "SeedVR2 Upscaler"
#define AppPublisher "SeedVR2 Upscaler"
#define AppExe "runtime\python\pythonw.exe"

[Setup]
AppId={{8B7459F5-CA81-4A41-988F-506E47192D64}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
DefaultDirName={code:GetDefaultDirName}
DefaultGroupName={#AppName}
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
SetupArchitecture=x64
MinVersion=10.0
WizardStyle=modern dynamic
SetupIconFile={#SourceRoot}\assets\seedvr2.ico
UninstallDisplayIcon={app}\assets\seedvr2.ico
UninstallDisplayName={cm:AppDisplayName}
UsePreviousAppDir=yes
UsePreviousTasks=yes
UsePreviousLanguage=yes
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage
OutputDir={#OutputDir}
OutputBaseFilename=SeedVR2-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=1900000000
SlicesPerDisk=1
RestartIfNeededByRun=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[CustomMessages]
english.AppDisplayName=SeedVR2 Upscaler
english.AppShortcutName=SeedVR2 Upscaler
english.UninstallShortcutName=Uninstall SeedVR2 Upscaler
english.AdditionalOptions=Additional options:
english.DesktopShortcut=Create a desktop shortcut
english.StartMenuShortcut=Create a Start Menu shortcut
english.LaunchAfterInstall=Launch SeedVR2 Upscaler after installation
english.InstallHint=For best performance, install on an SSD and keep at least 15 GB free on the destination drive.
english.CheckingCuda=Checking models, Runtime, and CUDA…
english.CudaCheckFailed=The post-install CUDA check failed with code %1. Check the NVIDIA display driver.
chinesesimplified.AppDisplayName=SeedVR2 图片放大工具
chinesesimplified.AppShortcutName=SeedVR2 图片放大工具
chinesesimplified.UninstallShortcutName=卸载 SeedVR2 图片放大工具
chinesesimplified.AdditionalOptions=附加选项：
chinesesimplified.DesktopShortcut=创建桌面快捷方式
chinesesimplified.StartMenuShortcut=创建开始菜单快捷方式
chinesesimplified.LaunchAfterInstall=安装完成后启动 SeedVR2 图片放大工具
chinesesimplified.InstallHint=建议选择固态硬盘安装，并为安装目录预留至少 15GB 可用空间。
chinesesimplified.CheckingCuda=正在检查模型、Runtime 和 CUDA…
chinesesimplified.CudaCheckFailed=安装后 CUDA 自检失败，错误代码：%1。请检查 NVIDIA 显卡驱动。

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:AdditionalOptions}"
Name: "startmenu"; Description: "{cm:StartMenuShortcut}"; GroupDescription: "{cm:AdditionalOptions}"

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{cm:AppShortcutName}"; Filename: "{app}\{#AppExe}"; Parameters: "-B -s -m app.gui"; WorkingDir: "{app}"; IconFilename: "{app}\assets\seedvr2.ico"; Tasks: desktopicon
Name: "{userprograms}\{#AppName}\{cm:AppShortcutName}"; Filename: "{app}\{#AppExe}"; Parameters: "-B -s -m app.gui"; WorkingDir: "{app}"; IconFilename: "{app}\assets\seedvr2.ico"; Tasks: startmenu
Name: "{userprograms}\{#AppName}\{cm:UninstallShortcutName}"; Filename: "{uninstallexe}"; Tasks: startmenu

[Registry]
Root: HKCU; Subkey: "Software\SeedVR2Upscaler"; ValueType: string; ValueName: "InstallLocation"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\SeedVR2Upscaler"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#AppVersion}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#AppExe}"; Parameters: "-B -s -m app.gui"; WorkingDir: "{app}"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent

[Code]
var
  InstallHintLabel: TNewStaticText;

function GetDefaultDirName(Param: String): String;
var
  RegisteredDir: String;
begin
  if RegQueryStringValue(HKCU, 'Software\SeedVR2Upscaler', 'InstallLocation', RegisteredDir) and (RegisteredDir <> '') then
    Result := RegisteredDir
  else if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\SeedVR2Upscaler', 'InstallLocation', RegisteredDir) and (RegisteredDir <> '') then
    Result := RegisteredDir
  else
    Result := ExpandConstant('{localappdata}\Programs\SeedVR2 Upscaler');
end;

procedure InitializeWizard;
begin
  InstallHintLabel := TNewStaticText.Create(WizardForm.SelectDirPage);
  InstallHintLabel.Parent := WizardForm.SelectDirPage;
  InstallHintLabel.Left := WizardForm.DirEdit.Left;
  InstallHintLabel.Top := WizardForm.DirEdit.Top + WizardForm.DirEdit.Height + ScaleY(10);
  InstallHintLabel.Width := WizardForm.DirBrowseButton.Left + WizardForm.DirBrowseButton.Width - InstallHintLabel.Left;
  InstallHintLabel.Height := ScaleY(38);
  InstallHintLabel.AutoSize := False;
  InstallHintLabel.WordWrap := True;
  InstallHintLabel.Font.Style := [fsBold];
  InstallHintLabel.Caption := CustomMessage('InstallHint');
end;

procedure SaveInitialAppLanguage;
var
  SettingsDirectory, SettingsFile, LanguageCode: String;
begin
  SettingsDirectory := ExpandConstant('{localappdata}\SeedVR2 Upscaler');
  SettingsFile := AddBackslash(SettingsDirectory) + 'settings.json';
  if FileExists(SettingsFile) then
    Exit;
  if CompareText(ExpandConstant('{language}'), 'chinesesimplified') = 0 then
    LanguageCode := 'zh_CN'
  else
    LanguageCode := 'en';
  if ForceDirectories(SettingsDirectory) then
    SaveStringToFile(SettingsFile, '{"language": "' + LanguageCode + '"}'#13#10, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := CustomMessage('CheckingCuda');
    ResultCode := -1;
    if (not Exec(
      ExpandConstant('{app}\runtime\python\python.exe'),
      '-B -m app.cli check --cuda',
      ExpandConstant('{app}'),
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode)) or (ResultCode <> 0) then
      RaiseException(FmtMessage(CustomMessage('CudaCheckFailed'), [IntToStr(ResultCode)]));
    SaveInitialAppLanguage;
  end;
end;

procedure DeletePythonCaches(const Directory: String);
var
  FindRec: TFindRec;
  ItemPath: String;
begin
  if FindFirst(AddBackslash(Directory) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
           ((FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and
           ((FindRec.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) = 0) then
        begin
          ItemPath := AddBackslash(Directory) + FindRec.Name;
          if CompareText(FindRec.Name, '__pycache__') = 0 then
            DelTree(ItemPath, True, True, True)
          else
            DeletePythonCaches(ItemPath);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure RemoveEmptyDirectories(const Directory: String);
var
  FindRec: TFindRec;
  ItemPath: String;
begin
  if FindFirst(AddBackslash(Directory) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
           ((FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and
           ((FindRec.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) = 0) then
        begin
          ItemPath := AddBackslash(Directory) + FindRec.Name;
          RemoveEmptyDirectories(ItemPath);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  RemoveDir(Directory);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDirectory: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDirectory := ExpandConstant('{app}');
    DeletePythonCaches(AppDirectory);
    RemoveEmptyDirectories(AppDirectory);
  end;
end;
