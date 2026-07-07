#define MyAppName "Hermes AI"
#define MyAppVersion "2.4.1"
#define MyAppExeName "Hermes-ia.exe"
#define MyAppPublisher "Hermes AI Project"
#define MyAppURL "https://github.com/felipesantoliver/hermes-ai"

[Setup]
AppId={{298C505F-3DA1-402A-8B52-0CD8CD9ED4F4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}

DefaultDirName={autopf}\Hermes-ia
DefaultGroupName=Hermes AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

LicenseFile=..\LICENSE
SetupIconFile=..\icon.ico
OutputDir=..\installer_output
OutputBaseFilename=Hermes-ia-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableWelcomePage=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "..\dist\Hermes-ia.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

Source: "scripts\DownloadFile.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "scripts\DownloadLlamaServer.ps1"; DestDir: "{tmp}"; Flags: dontcopy

[Dirs]
Name: "{app}\models"
Name: "{app}\data"
Name: "{app}\data\logs"

[Icons]
Name: "{group}\Hermes AI"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar Hermes AI"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Hermes AI"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar o Hermes AI agora"; Flags: nowait postinstall skipifsilent

[Code]
var
  GpuPage: TInputOptionWizardPage;
  DownloadOptPage: TWizardPage;
  ModelInfoLabel: TNewStaticText;
  DownloadCheckBox: TNewCheckBox;
  SkipInfoLabel: TNewStaticText;
  DownloadPage: TOutputProgressWizardPage;
  CancelDownloadButton: TNewButton;

  SelectedModelUrl: String;
  SelectedModelSizeMB: Int64;
  LogFilePath: String;

  { Sinalização de cancelamento do download em andamento (grupo 10: antes
    disso, uma vez que a etapa de pós-instalação começava, não havia
    NENHUMA forma de interromper o download — o botão Cancelar padrão do
    Inno Setup já vem desabilitado nessa fase, e o loop de espera rodava
    até terminar ou estourar o tempo máximo. Este botão próprio, mais o
    arquivo de sinalização lido pelos scripts .ps1, resolvem isso. }
  DownloadWasCancelled: Boolean;
  CurrentDownloadPidFile: String;
  CurrentCancelFile: String;

const
  WV2ClientGuid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WV2BootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';
  ModelBaseUrl = 'https://huggingface.co/QuantFactory/Qwen2.5-7B-Instruct-abliterated-v2-GGUF/resolve/main/';
  MaxDownloadWaitSeconds = 4 * 60 * 60;

function RunCaptureToFile(const CmdLine, OutFile: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/C ' + CmdLine + ' > "' + OutFile + '" 2>&1',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function DetectGpuNames(): String;
var
  TempFile: String;
  Lines: TArrayOfString;
  I: Integer;
begin
  Result := '';
  TempFile := ExpandConstant('{tmp}\hermes_gpu.txt');

  if RunCaptureToFile('wmic path win32_VideoController get name /format:list', TempFile) then
  begin
    if LoadStringsFromFile(TempFile, Lines) then
      for I := 0 to GetArrayLength(Lines) - 1 do
        if Pos('Name=', Lines[I]) = 1 then
          Result := Result + Copy(Lines[I], 6, MaxInt) + '|';
  end;

  if Result = '' then
  begin
    DeleteFile(TempFile);
    if RunCaptureToFile(
      'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"',
      TempFile) then
    begin
      if LoadStringsFromFile(TempFile, Lines) then
        for I := 0 to GetArrayLength(Lines) - 1 do
          if Trim(Lines[I]) <> '' then
            Result := Result + Trim(Lines[I]) + '|';
    end;
  end;
end;

function ClassifyGpu(const Names: String): Integer;
var
  U: String;
begin
  U := Uppercase(Names);
  Result := -1;

  if U = '' then
  begin
    Result := 3;
    Exit;
  end;

  if (Pos('RTX 30', U) > 0) or (Pos('RTX 40', U) > 0) or (Pos('RTX 50', U) > 0) or
     (Pos('RTX A', U) > 0) or (Pos('RX 6800', U) > 0) or (Pos('RX 6900', U) > 0) or
     (Pos('RX 7', U) > 0) then
  begin
    Result := 0;
    Exit;
  end;

  if (Pos('GTX 10', U) > 0) or (Pos('GTX 16', U) > 0) or (Pos('RX 580', U) > 0) or
     (Pos('RX 570', U) > 0) or (Pos('RX 480', U) > 0) or (Pos('RX 5', U) > 0) then
  begin
    Result := 1;
    Exit;
  end;

  if (Pos('INTEL', U) > 0) or (Pos('UHD GRAPHICS', U) > 0) or (Pos('HD GRAPHICS', U) > 0) or
     (Pos('VEGA', U) > 0) or (Pos('RADEON(TM) GRAPHICS', U) > 0) then
  begin
    Result := 2;
    Exit;
  end;

  Result := -1;
end;

function GetModelInfo(Index: Integer; var Url: String; var SizeMB: Int64; var Label_: String): Boolean;
begin
  Result := True;
  case Index of
    0: begin
         Url := ModelBaseUrl + 'Qwen2.5-7B-Instruct-abliterated-v2.Q8_0.gguf';
         SizeMB := 8100;
         Label_ := 'Qwen2.5-7B-Instruct-abliterated-v2-Q8_0 (alta qualidade, ~8.1 GB)';
       end;
    1: begin
         Url := ModelBaseUrl + 'Qwen2.5-7B-Instruct-abliterated-v2.Q4_K_M.gguf';
         SizeMB := 4700;
         Label_ := 'Qwen2.5-7B-Instruct-abliterated-v2-Q4_K_M (equilibrado, ~4.7 GB)';
       end;
    2: begin
         Url := ModelBaseUrl + 'Qwen2.5-7B-Instruct-abliterated-v2.Q2_K.gguf';
         SizeMB := 3100;
         Label_ := 'Qwen2.5-7B-Instruct-abliterated-v2-Q2_K (mais leve, ~3.1 GB)';
       end;
    3: begin
         Url := ModelBaseUrl + 'Qwen2.5-7B-Instruct-abliterated-v2.Q2_K.gguf';
         SizeMB := 3100;
         Label_ := 'Qwen2.5-7B-Instruct-abliterated-v2-Q2_K (recomendado para CPU, ~3.1 GB)';
       end;
    4: begin
         Url := ModelBaseUrl + 'Qwen2.5-7B-Instruct-abliterated-v2.Q4_K_M.gguf';
         SizeMB := 4700;
         Label_ := 'Qwen2.5-7B-Instruct-abliterated-v2-Q4_K_M (opção segura, ~4.7 GB)';
       end;
  else
    Result := False;
  end;
end;

function GetLlamaVariant(Index: Integer): String;
begin
  { llama-server precisa de um binário compatível com a GPU. Usamos Vulkan
    para as duas faixas de GPU dedicada (funciona em NVIDIA e AMD sem exigir
    a instalação separada do runtime CUDA) e CPU para os demais casos —
    incluindo "não sei", por segurança, já que rodar em CPU sempre funciona,
    só que mais devagar. }
  case Index of
    0, 1: Result := 'vulkan';
  else
    Result := 'cpu';
  end;
end;

function Utf8ToUnicode(const S: AnsiString): String;
var
  I, Len: Integer;
  B1, B2, B3: Byte;
  Code: LongInt;
begin
  { Decodificador simples de UTF-8 -> String Unicode (suficiente para os
    caracteres acentuados do português usados nas mensagens do instalador;
    não trata pares substitutos de 4 bytes, que não ocorrem aqui). }
  Result := '';
  Len := Length(S);
  I := 1;
  while I <= Len do
  begin
    B1 := Ord(S[I]);
    if B1 < $80 then
    begin
      Result := Result + Chr(B1);
      Inc(I);
    end
    else if (B1 and $E0) = $C0 then
    begin
      if I + 1 <= Len then
      begin
        B2 := Ord(S[I + 1]);
        Code := ((B1 and $1F) shl 6) or (B2 and $3F);
        Result := Result + Chr(Code);
      end;
      I := I + 2;
    end
    else if (B1 and $F0) = $E0 then
    begin
      if I + 2 <= Len then
      begin
        B2 := Ord(S[I + 1]);
        B3 := Ord(S[I + 2]);
        Code := ((B1 and $0F) shl 12) or ((B2 and $3F) shl 6) or (B3 and $3F);
        Result := Result + Chr(Code);
      end;
      I := I + 3;
    end
    else
    begin
      { Sequência de 4 bytes ou byte inválido: pula (não esperado no JSON) }
      I := I + 4;
    end;
  end;
end;

function ExtractJsonValue(const Json, Key: String): String;
var
  Needle: String;
  PStart, PEnd: Integer;
begin
  Result := '';
  Needle := '"' + Key + '":';
  PStart := Pos(Needle, Json);
  if PStart = 0 then Exit;
  PStart := PStart + Length(Needle);

  if (PStart <= Length(Json)) and (Json[PStart] = '"') then
  begin
    Inc(PStart);
    PEnd := PStart;
    while (PEnd <= Length(Json)) and (Json[PEnd] <> '"') do
      Inc(PEnd);
    Result := Copy(Json, PStart, PEnd - PStart);
  end
  else
  begin
    PEnd := PStart;
    while (PEnd <= Length(Json)) and (Json[PEnd] <> ',') and (Json[PEnd] <> '}') do
      Inc(PEnd);
    Result := Trim(Copy(Json, PStart, PEnd - PStart));
  end;
end;

function GetSelectedGpuIndex(): Integer;
var
  I: Integer;
begin
  Result := 4;
  for I := 0 to GpuPage.CheckListBox.Items.Count - 1 do
    if GpuPage.Values[I] then
    begin
      Result := I;
      Break;
    end;
end;

function HasEnoughDiskSpace(const Drive: String; const RequiredMB: Int64): Boolean;
var
  FreeBytes, TotalBytes: Int64;
begin
  Result := GetSpaceOnDisk64(Drive, FreeBytes, TotalBytes) and
    (FreeBytes >= RequiredMB * 1024 * 1024);
end;

function IsWebView2Installed(): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2ClientGuid, 'pv', Version) or
    RegQueryStringValue(HKLM32, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2ClientGuid, 'pv', Version) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2ClientGuid, 'pv', Version);
end;

function DownloadGenericFile(const Url, Destination: String): Boolean;
var
  ResultCode: Integer;
  Cmd: String;
begin
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command ' +
    '"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
    'Invoke-WebRequest -Uri ''' + Url + ''' -OutFile ''' + Destination + ''' -UseBasicParsing"';
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) and FileExists(Destination);
end;

procedure EnsureWebView2;
var
  BootstrapperPath: String;
  ResultCode: Integer;
begin
  if IsWebView2Installed() then
    Exit;

  if MsgBox(
    'O Hermes AI precisa do Microsoft Edge WebView2 Runtime, que não foi encontrado ' +
    'neste computador.' + #13#10#13#10 +
    'Deseja baixar e instalar agora? (é necessário acesso à internet)',
    mbConfirmation, MB_YESNO) = IDYES then
  begin
    BootstrapperPath := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
    if DownloadGenericFile(WV2BootstrapperUrl, BootstrapperPath) then
    begin
      if not Exec(BootstrapperPath, '/silent /install', '', SW_SHOW,
                   ewWaitUntilTerminated, ResultCode) then
        MsgBox(
          'Não foi possível instalar o Edge WebView2 Runtime automaticamente.' + #13#10 +
          'Baixe manualmente em: https://developer.microsoft.com/microsoft-edge/webview2/',
          mbError, MB_OK);
    end
    else
      MsgBox(
        'Falha ao baixar o Edge WebView2 Runtime. Verifique sua conexão e, se preferir, ' +
        'instale manualmente depois em: https://developer.microsoft.com/microsoft-edge/webview2/',
        mbError, MB_OK);
  end;
end;

{ Mata (se ainda existir) o processo PowerShell responsável pelo download
  atual, usando o PID que o próprio script .ps1 grava em CurrentDownloadPidFile
  assim que começa a rodar. /T mata também processos filhos; /F força o
  encerramento imediato. }
procedure KillCurrentDownloadProcess;
var
  PidStr: String;
  ResultCode: Integer;
begin
  if (CurrentDownloadPidFile = '') or not FileExists(CurrentDownloadPidFile) then
    Exit;
  if LoadStringFromFile(CurrentDownloadPidFile, PidStr) then
  begin
    PidStr := Trim(PidStr);
    if PidStr <> '' then
      Exec(ExpandConstant('{sys}\taskkill.exe'), '/PID ' + PidStr + ' /T /F', '',
        SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

{ Handler do botão "Cancelar download": sinaliza o cancelamento (arquivo lido
  pelo DownloadFile.ps1 dentro do loop do BITS, o que permite remover o job
  de forma limpa), mata o processo PowerShell em execução, e marca a flag
  global para que o loop de espera no lado do Inno Setup também saia
  imediatamente, sem esperar o timeout de 4 horas. }
procedure CancelDownloadButtonClick(Sender: TObject);
var
  ResultCode: Integer;
begin
  if MsgBox('Tem certeza que deseja cancelar o download?' + #13#10 +
     'O Hermes AI será instalado, mas você precisará baixar o modelo e/ou ' +
     'o motor de IA manualmente depois.', mbConfirmation, MB_YESNO) = IDYES then
  begin
    DownloadWasCancelled := True;
    if CurrentCancelFile <> '' then
      SaveStringToFile(CurrentCancelFile, '1', False);

    { O download do modelo usa BITS (Background Intelligent Transfer Service),
      um job gerenciado pelo próprio Windows, INDEPENDENTE do processo
      PowerShell que o criou. Só sinalizar o CancelFile e matar o processo
      não é suficiente: se o taskkill (abaixo, via KillCurrentDownloadProcess)
      acontecer antes do script .ps1 notar o sinal (ele só verifica 1x por
      segundo), o job do BITS continuaria baixando em segundo plano mesmo
      com o instalador achando que cancelou. Por isso removemos o job aqui
      diretamente e de forma síncrona, com garantia, em vez de depender só
      do script filho perceber a tempo. Não tem efeito nenhum se não houver
      job com esse nome (ex.: já era o download do llama-server, que não
      usa BITS). }
    Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -Command "Get-BitsTransfer -Name ''HermesAI-ModelDownload'' ' +
      '-ErrorAction SilentlyContinue | Remove-BitsTransfer -ErrorAction SilentlyContinue"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    KillCurrentDownloadProcess;
    CancelDownloadButton.Enabled := False;
    DownloadPage.SetText('Cancelando o download...', 'Aguarde, finalizando com segurança.');
  end;
end;

procedure DownloadModelWithProgress;
var
  ScriptPath, StatusPath, DestPath, Cmd, PidFilePath, CancelFilePath: String;
  StatusJson: AnsiString;
  DecodedJson, State, Msg: String;
  Percent: Integer;
  ResultCode: Integer;
  Elapsed: Integer;
begin
  ExtractTemporaryFile('DownloadFile.ps1');
  ScriptPath := ExpandConstant('{tmp}\DownloadFile.ps1');
  StatusPath := ExpandConstant('{tmp}\hermes_download_status.json');
  LogFilePath := ExpandConstant('{app}\data\logs\installer_download.log');
  DestPath := ExpandConstant('{app}\models\hermes-core.gguf');
  PidFilePath := ExpandConstant('{tmp}\hermes_download.pid');
  CancelFilePath := ExpandConstant('{tmp}\hermes_download.cancel');

  ForceDirectories(ExpandConstant('{app}\models'));
  ForceDirectories(ExpandConstant('{app}\data\logs'));
  DeleteFile(StatusPath);
  DeleteFile(PidFilePath);
  DeleteFile(CancelFilePath);

  DownloadWasCancelled := False;
  CurrentDownloadPidFile := PidFilePath;
  CurrentCancelFile := CancelFilePath;

  Cmd := Format(
    '-NoProfile -ExecutionPolicy Bypass -File "%s" -Url "%s" -Destination "%s" -StatusFile "%s" -LogFile "%s" -PidFile "%s" -CancelFile "%s"', [
    ScriptPath, SelectedModelUrl, DestPath, StatusPath, LogFilePath, PidFilePath, CancelFilePath]);

  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '',
              SW_HIDE, ewNoWait, ResultCode) then
  begin
    MsgBox('Não foi possível iniciar o download do modelo de IA.', mbError, MB_OK);
    Exit;
  end;

  DownloadPage.SetText('Iniciando download...', '');
  DownloadPage.SetProgress(0, 100);
  DownloadPage.Show;
  CancelDownloadButton.Visible := True;
  CancelDownloadButton.Enabled := True;
  try
    State := '';
    Elapsed := 0;
    repeat
      Sleep(1000);
      Inc(Elapsed);

      if LoadStringFromFile(StatusPath, StatusJson) then
      begin
        DecodedJson := Utf8ToUnicode(StatusJson);
        State := ExtractJsonValue(DecodedJson, 'state');
        Percent := StrToIntDef(ExtractJsonValue(DecodedJson, 'percent'), 0);
        Msg := ExtractJsonValue(DecodedJson, 'message');

        DownloadPage.SetProgress(Percent, 100);
        DownloadPage.SetText('Baixando o modelo de IA... (' + IntToStr(Percent) + '%)', Msg);
      end;
    { Além dos estados 'done'/'error', agora também saímos do loop se o
      usuário clicou em "Cancelar download" (DownloadWasCancelled) ou se o
      próprio script sinalizou o estado 'cancelled'. }
    until (State = 'done') or (State = 'error') or (State = 'cancelled') or
          DownloadWasCancelled or (Elapsed >= MaxDownloadWaitSeconds);

    if DownloadWasCancelled or (State = 'cancelled') then
      DownloadPage.SetText('Download cancelado.', 'Você pode baixar o modelo manualmente depois.')
    else if State = 'error' then
      MsgBox(
        'Ocorreu um erro no download do modelo de IA.' + #13#10 +
        'Detalhes: ' + Msg + #13#10#13#10 +
        'Log completo em: ' + LogFilePath + #13#10#13#10 +
        'Você pode baixar o modelo manualmente depois e colocá-lo em:' + #13#10 +
        DestPath, mbError, MB_OK)
    else if State <> 'done' then
      MsgBox(
        'O download não terminou dentro do tempo esperado.' + #13#10 +
        'Verifique sua conexão. Você pode tentar novamente depois ou baixar ' +
        'manualmente o modelo e colocá-lo em:' + #13#10 + DestPath,
        mbError, MB_OK)
    else
      DownloadPage.SetText('Download concluído!', '');
  finally
    CancelDownloadButton.Visible := False;
    DownloadPage.Hide;
  end;
end;

procedure DownloadLlamaServerWithProgress;
var
  ScriptPath, StatusPath, Cmd, Variant, PidFilePath: String;
  StatusJson: AnsiString;
  DecodedJson, State, Msg: String;
  Percent: Integer;
  ResultCode: Integer;
  Elapsed: Integer;
begin
  { Se o usuário já cancelou o download do modelo, não faz sentido seguir
    automaticamente para o download do llama-server. }
  if DownloadWasCancelled then
    Exit;

  ExtractTemporaryFile('DownloadLlamaServer.ps1');
  ScriptPath := ExpandConstant('{tmp}\DownloadLlamaServer.ps1');
  StatusPath := ExpandConstant('{tmp}\hermes_llama_status.json');
  Variant := GetLlamaVariant(GetSelectedGpuIndex());
  PidFilePath := ExpandConstant('{tmp}\hermes_llama_download.pid');
  DeleteFile(StatusPath);
  DeleteFile(PidFilePath);

  DownloadWasCancelled := False;
  CurrentDownloadPidFile := PidFilePath;
  CurrentCancelFile := ''; { este script baixa de forma síncrona; matar o
                             processo via PID é suficiente para cancelar }

  Cmd := Format(
    '-NoProfile -ExecutionPolicy Bypass -File "%s" -Variant "%s" -DestDir "%s" -StatusFile "%s" -LogFile "%s" -PidFile "%s"', [
    ScriptPath, Variant, ExpandConstant('{app}'), StatusPath, LogFilePath, PidFilePath]);

  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '',
              SW_HIDE, ewNoWait, ResultCode) then
  begin
    MsgBox('Não foi possível iniciar o download do motor de IA (llama-server).', mbError, MB_OK);
    Exit;
  end;

  DownloadPage.SetText('Baixando o motor de IA (llama-server)...', '');
  DownloadPage.SetProgress(0, 100);
  DownloadPage.Show;
  CancelDownloadButton.Visible := True;
  CancelDownloadButton.Enabled := True;
  try
    State := '';
    Elapsed := 0;
    { O pacote do llama-server é bem menor que o modelo (dezenas/poucas
      centenas de MB), então usamos o mesmo teto de segurança do modelo,
      mas na prática ele termina bem antes disso. }
    repeat
      Sleep(1000);
      Inc(Elapsed);

      if LoadStringFromFile(StatusPath, StatusJson) then
      begin
        DecodedJson := Utf8ToUnicode(StatusJson);
        State := ExtractJsonValue(DecodedJson, 'state');
        Percent := StrToIntDef(ExtractJsonValue(DecodedJson, 'percent'), 0);
        Msg := ExtractJsonValue(DecodedJson, 'message');

        DownloadPage.SetProgress(Percent, 100);
        DownloadPage.SetText('Baixando o motor de IA... (' + IntToStr(Percent) + '%)', Msg);
      end;
    until (State = 'done') or (State = 'error') or DownloadWasCancelled or
          (Elapsed >= MaxDownloadWaitSeconds);

    if DownloadWasCancelled then
      DownloadPage.SetText('Download cancelado.', 'Você pode instalar o motor de IA manualmente depois.')
    else if State = 'error' then
      MsgBox(
        'Ocorreu um erro ao baixar o motor de IA (llama-server).' + #13#10 +
        'Detalhes: ' + Msg + #13#10#13#10 +
        'Log completo em: ' + LogFilePath + #13#10#13#10 +
        'O Hermes AI foi instalado, mas o chat não vai funcionar até você ' +
        'instalar o llama-server manualmente (releases em ' +
        'https://github.com/ggml-org/llama.cpp/releases) em:' + #13#10 +
        ExpandConstant('{app}'), mbError, MB_OK)
    else if State <> 'done' then
      MsgBox(
        'O download do motor de IA não terminou dentro do tempo esperado.' + #13#10 +
        'Verifique sua conexão. O Hermes AI foi instalado, mas o chat não vai ' +
        'funcionar até o llama-server ser instalado (manualmente, se preciso) em:' + #13#10 +
        ExpandConstant('{app}'), mbError, MB_OK)
    else
      DownloadPage.SetText('Motor de IA instalado!', '');
  finally
    CancelDownloadButton.Visible := False;
    DownloadPage.Hide;
  end;
end;

procedure InitializeWizard;
var
  DetectedIndex: Integer;
begin
  GpuPage := CreateInputOptionPage(wpSelectDir,
    'Selecione sua placa de vídeo',
    'Isso ajuda o Hermes a escolher a versão certa do modelo de IA para o seu computador.',
    'Se não tiver certeza, escolha "Não sei" - baixaremos uma versão equilibrada e segura.',
    True, False);

  GpuPage.Add('NVIDIA RTX 3060 ou superior (8 GB de VRAM ou mais)');
  GpuPage.Add('NVIDIA GTX 1050 a 1080 / AMD RX 580 ou equivalente (4 a 8 GB de VRAM)');
  GpuPage.Add('Placa de vídeo integrada ou antiga (Intel HD Graphics, etc.)');
  GpuPage.Add('Apenas CPU (sem placa de vídeo dedicada)');
  GpuPage.Add('Não sei / prefiro a opção mais segura');

  DetectedIndex := ClassifyGpu(DetectGpuNames());
  if DetectedIndex = -1 then
    DetectedIndex := 4;
  GpuPage.Values[DetectedIndex] := True;

  DownloadOptPage := CreateCustomPage(GpuPage.ID,
    'Download do modelo de IA',
    'O Hermes precisa de um modelo de linguagem (.gguf) para funcionar.');

  ModelInfoLabel := TNewStaticText.Create(DownloadOptPage);
  ModelInfoLabel.Parent := DownloadOptPage.Surface;
  ModelInfoLabel.Left := 0;
  ModelInfoLabel.Top := 0;
  ModelInfoLabel.Width := DownloadOptPage.SurfaceWidth;
  ModelInfoLabel.WordWrap := True;
  ModelInfoLabel.Caption := '';

  DownloadCheckBox := TNewCheckBox.Create(DownloadOptPage);
  DownloadCheckBox.Parent := DownloadOptPage.Surface;
  DownloadCheckBox.Left := 0;
  DownloadCheckBox.Top := ModelInfoLabel.Top + 40;
  DownloadCheckBox.Width := DownloadOptPage.SurfaceWidth;
  DownloadCheckBox.Caption := 'Baixar o modelo e o motor de IA agora (recomendado)';
  DownloadCheckBox.Checked := True;

  SkipInfoLabel := TNewStaticText.Create(DownloadOptPage);
  SkipInfoLabel.Parent := DownloadOptPage.Surface;
  SkipInfoLabel.Left := 0;
  SkipInfoLabel.Top := DownloadCheckBox.Top + 30;
  SkipInfoLabel.Width := DownloadOptPage.SurfaceWidth;
  SkipInfoLabel.WordWrap := True;
  SkipInfoLabel.Caption :=
    'Se preferir pular esta etapa (ex.: internet lenta), o Hermes AI será instalado ' +
    'sem o modelo e sem o motor de IA (llama-server). Depois, baixe o arquivo .gguf e ' +
    'coloque em "models\hermes-core.gguf", e baixe o llama-server em ' +
    'github.com/ggml-org/llama.cpp/releases, extraindo o conteúdo direto na pasta ' +
    'de instalação (ao lado de Hermes-ia.exe).';

  DownloadPage := CreateOutputProgressPage(
    'Baixando o modelo de IA',
    'Isso pode levar alguns minutos, dependendo da sua internet.');

  { Botão próprio de cancelamento: a página de progresso (TOutputProgressWizardPage)
    não expõe um botão de cancelar nativo, e a etapa de pós-instalação
    (ssPostInstall) já desabilita por padrão o botão Cancelar do rodapé do
    Inno Setup. Sem este botão, o usuário ficava sem NENHUMA forma de
    interromper o download. Fica escondido até um download começar. }
  CancelDownloadButton := TNewButton.Create(WizardForm);
  CancelDownloadButton.Parent := WizardForm;
  CancelDownloadButton.Width := 140;
  CancelDownloadButton.Height := WizardForm.CancelButton.Height;
  { Ancorado à ESQUERDA do botão Cancelar nativo (não a ClientWidth): assim
    nunca se sobrepõe a ele nem ao botão Avançar, independentemente do
    tamanho da janela ou de mudanças futuras no layout padrão do wizard. }
  CancelDownloadButton.Left := WizardForm.CancelButton.Left - CancelDownloadButton.Width - 10;
  CancelDownloadButton.Top := WizardForm.CancelButton.Top;
  CancelDownloadButton.Caption := 'Cancelar download';
  CancelDownloadButton.OnClick := @CancelDownloadButtonClick;
  CancelDownloadButton.Visible := False;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Url, Label_: String;
  SizeMB: Int64;
begin
  if CurPageID = DownloadOptPage.ID then
  begin
    GetModelInfo(GetSelectedGpuIndex(), Url, SizeMB, Label_);
    SelectedModelUrl := Url;
    SelectedModelSizeMB := SizeMB;
    ModelInfoLabel.Caption := 'Modelo selecionado: ' + Label_;
  end;

  if CurPageID = wpFinished then
  begin
    if (not DownloadCheckBox.Checked) or DownloadWasCancelled then
      WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
        'Lembre-se: o modelo de IA e/ou o motor de IA não foram baixados agora' + #13#10 +
        '(não selecionado ou download cancelado).' + #13#10 +
        'Modelo (.gguf) recomendado: ' + SelectedModelUrl + #13#10 +
        'Coloque-o em: ' + ExpandConstant('{app}') + '\models\hermes-core.gguf' + #13#10#13#10 +
        'Motor de IA (llama-server): baixe em github.com/ggml-org/llama.cpp/releases ' +
        'e extraia o conteúdo direto em: ' + ExpandConstant('{app}');
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Drive: String;
  RequiredMB: Int64;
begin
  Result := True;

  if (CurPageID = DownloadOptPage.ID) and DownloadCheckBox.Checked then
  begin
    Drive := ExtractFileDrive(WizardDirValue);
    { +500 MB de folga para arquivos do programa/logs, +300 MB para o
      pacote do llama-server (bem menor que o modelo, mas soma). }
    RequiredMB := SelectedModelSizeMB + 500 + 300;
    if not HasEnoughDiskSpace(Drive, RequiredMB) then
    begin
      MsgBox(
        'Espaço em disco insuficiente em ' + Drive + #13#10 +
        'São necessários pelo menos ' + IntToStr(RequiredMB) + ' MB livres ' +
        '(modelo de IA + arquivos do programa).',
        mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    EnsureWebView2;

    if DownloadCheckBox.Checked then
    begin
      DownloadModelWithProgress;
      DownloadLlamaServerWithProgress;
    end;
  end;
end;
