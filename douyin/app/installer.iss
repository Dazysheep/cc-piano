; cc-piano 安装程序（由 app\build_app.py 调用 ISCC 编译）
; /DSourceDir=dist\QinfangStudio  /DOutDir=dist\installer  /DIconFile=icon.ico

#define AppName "cc-piano"
#ifndef AppVer
  #define AppVer "dev"
#endif

[Setup]
AppId={{6E1B6A2C-0F4D-4E0B-9C1F-3B7D2E5A9C41}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=cc-engine
DefaultDirName={code:DefaultDir}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 软件会在安装目录里写成片、图库、草稿素材，所以装在用户可写的位置，不需要管理员权限
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename=cc-piano_v{#AppVer}_安装程序
VersionInfoVersion={#AppVer}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} {#AppVer} 安装程序
AppVerName={#AppName} {#AppVer}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\cc-piano.exe
Compression=lzma2/fast
SolidCompression=no
; 模型和依赖压缩后超过 2GB，分卷：setup.exe + cc-piano_v<版本>_安装程序-1.bin …（放在同一个文件夹里运行 setup.exe）
DiskSpanning=yes
DiskSliceSize=2000000000
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "chs"; MessagesFile: "compiler:Default.isl"

[Messages]
; 安装向导界面的中文（本机 Inno Setup 没有自带简体中文语言包）
SetupWindowTitle=安装 - %1
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonOK=确定
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&R)...
ButtonWizardBrowse=浏览(&R)...
ExitSetupTitle=退出安装
ExitSetupMessage=安装还没有完成。现在退出的话，程序不会被安装。%n%n以后可以再运行安装程序完成安装。%n%n确定退出吗？
WelcomeLabel1=欢迎安装 [name]
WelcomeLabel2=将在这台电脑上安装 [name/ver]。%n%n钢琴下落音符、音轨剪辑、拨片开头、发布台、作品库，一个窗口里完成。
WizardSelectDir=选择安装位置
SelectDirDesc=[name] 要装在哪里？
SelectDirLabel3=安装程序会把 [name] 装到下面的文件夹（成片、模型都在这里，建议放在空间大的磁盘）。
SelectDirBrowseLabel=点“下一步”继续；要换文件夹请点“浏览”。
DiskSpaceGBLabel=至少需要 [gb] GB 可用空间。
DiskSpaceMBLabel=至少需要 [mb] MB 可用空间。
WizardSelectTasks=附加选项
SelectTasksDesc=还需要做什么？
SelectTasksLabel2=选择安装 [name] 时要做的事，然后点“下一步”。
WizardReady=准备安装
ReadyLabel1=已经准备好安装 [name]。
ReadyLabel2a=点“安装”开始；要修改设置请点“上一步”。
ReadyLabel2b=点“安装”开始。
ReadyMemoDir=安装位置：
ReadyMemoTasks=附加选项：
WizardInstalling=正在安装
InstallingLabel=正在安装 [name]，文件较多，请稍候……
FinishedHeadingLabel=[name] 安装完成
FinishedLabelNoIcons=[name] 已安装到这台电脑。
FinishedLabel=[name] 已安装到这台电脑，可以从开始菜单或桌面快捷方式打开。
ClickFinish=点“完成”退出安装程序。
StatusExtractFiles=正在解压文件……
StatusCreateIcons=正在创建快捷方式……
StatusRunProgram=正在完成安装……
DirExistsTitle=文件夹已存在
DirExists=文件夹：%n%n%1%n%n已经存在。仍然装到这里吗？
DiskSpaceWarningTitle=磁盘空间不足
DiskSpaceWarning=安装至少需要 %1 KB 可用空间，但所选磁盘只有 %2 KB。%n%n仍然继续吗？
ConfirmUninstall=确定要删除 %1 吗？（待上传的成片不会被删除）
UninstalledAll=%1 已从这台电脑上删除。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
; 旧版启动程序（琴房Studio.exe）和运行时产生的个人数据不打包：保存位置设置、网页缓存/日志（uploads）、中间文件、成片
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "\琴房Studio.exe,\douyin\publish\profile\*,\douyin\app_settings.json,\douyin\uploads\*,\douyin\output\*,\douyin\待上传\*"

[Dirs]
Name: "{app}\douyin\uploads"
Name: "{app}\douyin\output"
Name: "{app}\douyin\待上传"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\cc-piano.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\cc-piano.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\cc-piano.exe"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; 旧版叫「琴房 Studio」：覆盖安装时删掉旧的启动程序和快捷方式
Type: files; Name: "{app}\琴房Studio.exe"
Type: files; Name: "{autoprograms}\琴房 Studio.lnk"
Type: files; Name: "{autodesktop}\琴房 Studio.lnk"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\douyin\uploads"

[Code]
function DefaultDir(Param: String): String;
begin
  { 有 D 盘就装到 D 盘（成片、模型都很占空间） }
  if DirExists('D:\') then
    Result := 'D:\QinfangStudio'
  else
    Result := ExpandConstant('{localappdata}\Programs\QinfangStudio');
end;
