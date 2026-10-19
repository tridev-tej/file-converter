[Setup]
AppId=com.tejeshvaish.fileconverter
AppName=FileConverter
AppVersion=1.0.0
AppPublisher=Tejesh Vaish
DefaultDirName={localappdata}\Programs\FileConverter
DefaultGroupName=FileConverter
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=FileConverter-Windows-x64-Setup
SetupIconFile=..\build\icons\FileConverter.ico
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
ChangesEnvironment=yes

[Tasks]
Name: "clipath"; Description: "Add FileConverter CLI to my PATH"; Flags: unchecked

[Files]
Source: "..\dist\FileConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FileConverter"; Filename: "{app}\FileConverter.exe"
Name: "{group}\Uninstall FileConverter"; Filename: "{uninstallexe}"

[Code]
procedure UpdatePath(Add: Boolean);
var Existing, Entry, Updated: String;
begin
  Entry := ExpandConstant('{app}');
  RegQueryStringValue(HKCU, 'Environment', 'Path', Existing);
  if Add then begin
    if Pos(';' + Lowercase(Entry) + ';', ';' + Lowercase(Existing) + ';') = 0 then begin
      if Existing = '' then Updated := Entry else Updated := Existing + ';' + Entry;
      if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Updated) then
        RaiseException('Could not update user PATH');
      RegWriteDWordValue(HKCU, 'Software\FileConverter', 'PathAdded', 1);
    end;
  end else begin
    Updated := ';' + Existing + ';';
    StringChangeEx(Updated, ';' + Entry + ';', ';', True);
    if (Length(Updated) > 0) and (Updated[1] = ';') then Delete(Updated, 1, 1);
    if (Length(Updated) > 0) and (Updated[Length(Updated)] = ';') then Delete(Updated, Length(Updated), 1);
    if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Updated) then
      RaiseException('Could not remove CLI from user PATH');
    RegDeleteValue(HKCU, 'Software\FileConverter', 'PathAdded');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('clipath') then UpdatePath(True);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Added: Cardinal;
begin
  if (CurUninstallStep = usUninstall) and RegQueryDWordValue(HKCU, 'Software\FileConverter', 'PathAdded', Added) then
    if Added = 1 then UpdatePath(False);
end;
