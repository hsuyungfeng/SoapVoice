; soapvoice.iss
; Inno Setup 安裝腳本 for SoapVoice 醫療語音轉 SOAP 病歷系統
; 版本: 0.8.0
; 編譯命令: iscc installer/soapvoice.iss

[Setup]
AppName=SoapVoice
AppVersion=0.8.0
AppPublisher=SoapVoice Team
AppPublisherURL=https://github.com/yourusername/SoapVoice
AppSupportURL=https://github.com/yourusername/SoapVoice/issues
AppUpdatesURL=https://github.com/yourusername/SoapVoice/releases
DefaultDirName={pf}\SoapVoice
DefaultGroupName=SoapVoice
UninstallDisplayIcon={app}\SoapVoice.exe
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=installer\
PrivilegesRequired=admin
; 無訊息安裝參數支援 (預設內建)
SetupLogging=yes
; 安裝程式圖示（可選）
; SetupIconFile=installer\icon.ico
; 授權檔案（可選）
; LicenseFile=installer\license.txt
; 安裝程式橫幅圖片（可選）
; WizardImageFile=installer\banner.bmp

[Files]
; 主要執行檔（單一 EXE，已嵌入所有模型與資料）
Source: "dist\SoapVoice.exe"; DestDir: "{app}"; Flags: ignoreversion
; 若模型與資料未嵌入 EXE，可取消註解以下行：
; Source: "models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs
; Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs
; 包含 .env 檔案（若需要）
; Source: ".env"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SoapVoice"; Filename: "{app}\SoapVoice.exe"
Name: "{group}\Uninstall SoapVoice"; Filename: "{uninstallexe}"
Name: "{commondesktop}\SoapVoice"; Filename: "{app}\SoapVoice.exe"

[Run]
; 安裝後啟動應用程式（可選，跳過無訊息安裝）
Filename: "{app}\SoapVoice.exe"; Description: "Launch SoapVoice"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; 刪除使用者資料目錄（避免殘留檔案）
Type: filesandordirs; Name: "{localappdata}\SoapVoice"
; 刪除其他可能的使用者目錄（如錄音檔）
Type: filesandordirs; Name: "{userappdata}\SoapVoice"

[Code]
// 自訂 Pascal 腳本（可選），用於更進階的安裝邏輯
// 例如：檢查 .NET Framework 版本、設定環境變數等
function InitializeSetup(): Boolean;
begin
  // 預設允許安裝
  Result := True;
end;