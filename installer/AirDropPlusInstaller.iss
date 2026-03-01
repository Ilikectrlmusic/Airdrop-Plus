#define MyAppName "AirDrop Plus"
#define MyAppVersion "1.5"
#define MyAppPublisher "Ilikectrlmusic"
#define MyAppURL "https://github.com/Ilikectrlmusic/Airdrop-Plus"
#define MyAppExeName "AirDropPlus.exe"

[Setup]
AppId={{9D2C8B7E-6F5B-4F80-B5ED-790A4D56FBA9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
WizardStyle=modern dynamic
SetupIconFile=..\static\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir=..\dist\installer
OutputBaseFilename=AirDropPlus-Setup
Compression=lzma2
SolidCompression=yes
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage
UsePreviousAppDir=yes
UsePreviousTasks=no
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
RestartApplications=no
WizardSizePercent=100

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[CustomMessages]
english.InstallOptionsTitle=Installation Options
english.InstallOptionsDesc=Choose install path and shortcut options.
english.InstallDirLabel=Install location:
english.BrowseButton=Browse...
english.DesktopShortcut=Create desktop shortcut
english.StartMenuShortcut=Create Start Menu shortcut
english.InvalidInstallDir=Please choose a valid install location.
english.BonjourInstallFailed=Bonjour installation failed (exit code: %1).
english.LaunchProgram=Run %1

chinesesimplified.InstallOptionsTitle=安装选项
chinesesimplified.InstallOptionsDesc=请选择安装位置与快捷方式选项。
chinesesimplified.InstallDirLabel=安装位置：
chinesesimplified.BrowseButton=浏览...
chinesesimplified.DesktopShortcut=创建桌面快捷方式
chinesesimplified.StartMenuShortcut=创建开始菜单快捷方式
chinesesimplified.InvalidInstallDir=请选择有效的安装位置。
chinesesimplified.BonjourInstallFailed=Bonjour 安装失败（退出码：%1）。
chinesesimplified.LaunchProgram=运行 %1

[Files]
Source: "..\dist\AirDropPlus\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "Bonjour64.msi"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\{#MyAppName}.lnk"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Check: ShouldCreateStartMenuShortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Check: ShouldCreateDesktopShortcut

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
var
  InstallOptionsPage: TWizardPage;
  InstallDirEdit: TNewEdit;
  DesktopShortcutCheck: TNewCheckBox;
  StartMenuShortcutCheck: TNewCheckBox;
  CreateDesktopShortcut: Boolean;
  CreateStartMenuShortcut: Boolean;

function IsChineseLanguage: Boolean;
begin
  Result := (ActiveLanguage = 'chinesesimplified');
end;

function T(const EnText: String; const ZhText: String): String;
begin
  if IsChineseLanguage then
    Result := ZhText
  else
    Result := EnText;
end;

procedure BrowseInstallDirClick(Sender: TObject);
var
  SelectedDir: String;
begin
  SelectedDir := InstallDirEdit.Text;
  if BrowseForFolder(CustomMessage('InstallDirLabel'), SelectedDir, True) then
    InstallDirEdit.Text := SelectedDir;
end;

procedure StopRunningApp();
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{cmd}'),
    '/C taskkill /F /IM {#MyAppExeName} /T >nul 2>&1',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

procedure RemoveAutoStartRegistry();
begin
  RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'AirDropPlus');
  RegDeleteValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Run', 'AirDropPlus');
  RegDeleteValue(HKLM64, 'Software\Microsoft\Windows\CurrentVersion\Run', 'AirDropPlus');
end;

function IsBonjourInstalled: Boolean;
var
  Dummy: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Services\Bonjour Service', 'ImagePath', Dummy) or
    RegQueryStringValue(HKLM64, 'SYSTEM\CurrentControlSet\Services\Bonjour Service', 'ImagePath', Dummy) or
    RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Services\mDNSResponder', 'ImagePath', Dummy) or
    RegQueryStringValue(HKLM64, 'SYSTEM\CurrentControlSet\Services\mDNSResponder', 'ImagePath', Dummy);
end;

function InstallBonjour(var ExitCode: Integer): Boolean;
var
  MsiPath: String;
begin
  ExtractTemporaryFile('Bonjour64.msi');
  MsiPath := ExpandConstant('{tmp}\Bonjour64.msi');

  if not Exec(
    ExpandConstant('{sys}\msiexec.exe'),
    '/i "' + MsiPath + '" /qn /norestart',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ExitCode
  ) then
  begin
    ExitCode := -1;
    Result := False;
    Exit;
  end;

  Result := (ExitCode = 0) or (ExitCode = 3010) or (ExitCode = 1641);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  BonjourExitCode: Integer;
begin
  Result := '';

  StopRunningApp();

  if not IsBonjourInstalled then
  begin
    if not InstallBonjour(BonjourExitCode) then
      Result := FmtMessage(CustomMessage('BonjourInstallFailed'), [IntToStr(BonjourExitCode)]);
  end;
end;

procedure InitializeWizard();
var
  InstallDirLabel: TNewStaticText;
  BrowseButton: TNewButton;
begin
  InstallOptionsPage := CreateCustomPage(
    wpLicense,
    CustomMessage('InstallOptionsTitle'),
    CustomMessage('InstallOptionsDesc')
  );

  InstallDirLabel := TNewStaticText.Create(WizardForm);
  InstallDirLabel.Parent := InstallOptionsPage.Surface;
  InstallDirLabel.Caption := CustomMessage('InstallDirLabel');
  InstallDirLabel.Left := ScaleX(0);
  InstallDirLabel.Top := ScaleY(6);

  InstallDirEdit := TNewEdit.Create(WizardForm);
  InstallDirEdit.Parent := InstallOptionsPage.Surface;
  InstallDirEdit.Left := ScaleX(0);
  InstallDirEdit.Top := InstallDirLabel.Top + InstallDirLabel.Height + ScaleY(6);
  InstallDirEdit.Width := InstallOptionsPage.SurfaceWidth - ScaleX(96);
  InstallDirEdit.Text := WizardDirValue;

  BrowseButton := TNewButton.Create(WizardForm);
  BrowseButton.Parent := InstallOptionsPage.Surface;
  BrowseButton.Caption := CustomMessage('BrowseButton');
  BrowseButton.Width := ScaleX(88);
  BrowseButton.Left := InstallDirEdit.Left + InstallDirEdit.Width + ScaleX(8);
  BrowseButton.Top := InstallDirEdit.Top;
  BrowseButton.Height := InstallDirEdit.Height;
  BrowseButton.OnClick := @BrowseInstallDirClick;

  DesktopShortcutCheck := TNewCheckBox.Create(WizardForm);
  DesktopShortcutCheck.Parent := InstallOptionsPage.Surface;
  DesktopShortcutCheck.Caption := CustomMessage('DesktopShortcut');
  DesktopShortcutCheck.Left := ScaleX(0);
  DesktopShortcutCheck.Width := InstallOptionsPage.SurfaceWidth;
  DesktopShortcutCheck.Height := ScaleY(26);
  DesktopShortcutCheck.Top := InstallDirEdit.Top + InstallDirEdit.Height + ScaleY(18);
  DesktopShortcutCheck.Checked := True;

  StartMenuShortcutCheck := TNewCheckBox.Create(WizardForm);
  StartMenuShortcutCheck.Parent := InstallOptionsPage.Surface;
  StartMenuShortcutCheck.Caption := CustomMessage('StartMenuShortcut');
  StartMenuShortcutCheck.Left := ScaleX(0);
  StartMenuShortcutCheck.Width := InstallOptionsPage.SurfaceWidth;
  StartMenuShortcutCheck.Height := ScaleY(26);
  StartMenuShortcutCheck.Top := DesktopShortcutCheck.Top + DesktopShortcutCheck.Height + ScaleY(4);
  StartMenuShortcutCheck.Checked := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  DirValue: String;
begin
  Result := True;

  if CurPageID = InstallOptionsPage.ID then
  begin
    DirValue := Trim(InstallDirEdit.Text);
    if DirValue = '' then
    begin
      MsgBox(CustomMessage('InvalidInstallDir'), mbError, MB_OK);
      Result := False;
      Exit;
    end;

    WizardForm.DirEdit.Text := DirValue;
    CreateDesktopShortcut := DesktopShortcutCheck.Checked;
    CreateStartMenuShortcut := StartMenuShortcutCheck.Checked;
  end;
end;

function ShouldCreateDesktopShortcut: Boolean;
begin
  Result := CreateDesktopShortcut;
end;

function ShouldCreateStartMenuShortcut: Boolean;
begin
  Result := CreateStartMenuShortcut;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    StopRunningApp();
    RemoveAutoStartRegistry();
  end;
end;
