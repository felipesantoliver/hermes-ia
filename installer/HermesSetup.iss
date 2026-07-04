; ============================================================================
;  HermesSetup.iss
;  Instalador Windows do Hermes AI (Inno Setup 6.x)
; ----------------------------------------------------------------------------
;  Fluxo do instalador:
;    1. Boas-vindas + licença MIT
;    2. Escolha da pasta de instalação
;    3. Detecção/seleção da placa de vídeo
;    4. Escolha: baixar o modelo agora ou pular
;    5. Instalação do Hermes-ia.exe
;    6. (pós-instalação) checa WebView2, baixa o modelo se escolhido
;    7. Atalhos + opção de executar ao finalizar
;
;  Pré-requisitos para compilar:
;    - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;    - dist\Hermes-ia.exe já gerado (rode build.py antes)
;    - Este arquivo deve estar em <raiz-do-repo>\installer\HermesSetup.iss
;      (os caminhos "..\" abaixo assumem essa estrutura)
;
;  Compilar: ISCC.exe installer\HermesSetup.iss
; ============================================================================

#define MyAppName "Hermes AI"
#define MyAppVersion "2.3.0"
#define MyAppExeName "Hermes-ia.exe"
#define MyAppPublisher "Hermes AI Project"
#define MyAppURL "https://github.com/felipesantoliver/hermes-ai"

[Setup]
; IMPORTANTE: gere um GUID novo e único para o seu projeto (no Inno Setup IDE:
; Tools > Generate GUID) e NUNCA mude depois do primeiro lançamento, senão o
; Windows trata como um programa diferente e não consegue atualizar/desinstalar.
AppId={{298C505F-3DA1-402A-8B52-0CD8CD9ED4F4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}

; --- Diretório padrão e privilégios ---
; {autopf} resolve para "C:\Program Files" se o usuário optar por instalar
; para todos os usuários (aí sim pede elevação), ou para
; "%LocalAppData%\Programs" se optar por instalar só para si (sem admin).
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
; O executável já compilado (backend + frontend embutidos) - obrigatório
Source: "..\dist\Hermes-ia.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Script de download embutido no instalador, mas não extraído automaticamente
; (Flags: dontcopy) - só vai para {tmp} quando chamarmos ExtractTemporaryFile.
Source: "scripts\DownloadFile.ps1"; DestDir: "{tmp}"; Flags: dontcopy

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
// ============================================================================
// VARIÁVEIS GLOBAIS
// ============================================================================
var
  GpuPage: TInputOptionWizardPage;         // tela de seleção da placa de vídeo
  DownloadOptPage: TWizardPage;            // tela "baixar agora ou depois?"
  ModelInfoLabel: TNewStaticText;
  DownloadCheckBox: TNewCheckBox;
  SkipInfoLabel: TNewStaticText;
  DownloadPage: TOutputProgressWizardPage; // barra de progresso do download

  SelectedModelUrl: String;
  SelectedModelSizeMB: Int64;
  LogFilePath: String;

const
  // GUID oficial do runtime Microsoft Edge WebView2 (Evergreen)
  WV2ClientGuid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WV2BootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';


// ============================================================================
// DETECÇÃO DE GPU
// ============================================================================

// Executa um comando via cmd.exe redirecionando a saída para um arquivo,
// já que o Exec() do Inno Setup não devolve o stdout diretamente.
function RunCaptureToFile(const CmdLine, OutFile: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/C ' + CmdLine + ' > "' + OutFile + '" 2>&1',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

// Tenta descobrir o(s) nome(s) da(s) placa(s) de vídeo instaladas.
// Primeiro via WMIC (mais rápido); se não existir/retornar vazio (comum em
// builds recentes do Windows 11, onde o WMIC foi removido), cai para
// PowerShell com Get-CimInstance.
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

// Classifica a(s) GPU(s) encontrada(s) em um dos 4 níveis do instalador.
// Retorna: 0=forte, 1=média, 2=fraca/integrada, 3=apenas CPU, -1=indefinido
// (nesse caso a tela pré-seleciona "Não sei" e deixa o usuário decidir).
function ClassifyGpu(const Names: String): Integer;
var
  U: String;
begin
  U := Uppercase(Names);
  Result := -1;

  if U = '' then
  begin
    Result := 3; // nenhuma placa dedicada detectada -> assume CPU
    Exit;
  end;

  // Placas fortes: RTX 30xx/40xx/50xx, RTX Axxx, RX 6800+/7xxx
  if (Pos('RTX 30', U) > 0) or (Pos('RTX 40', U) > 0) or (Pos('RTX 50', U) > 0) or
     (Pos('RTX A', U) > 0) or (Pos('RX 6800', U) > 0) or (Pos('RX 6900', U) > 0) or
     (Pos('RX 7', U) > 0) then
  begin
    Result := 0;
    Exit;
  end;

  // Placas medianas: GTX 10xx/16xx, RX 480/570/580, RX 5xxx
  if (Pos('GTX 10', U) > 0) or (Pos('GTX 16', U) > 0) or (Pos('RX 580', U) > 0) or
     (Pos('RX 570', U) > 0) or (Pos('RX 480', U) > 0) or (Pos('RX 5', U) > 0) then
  begin
    Result := 1;
    Exit;
  end;

  // Placas integradas/antigas
  if (Pos('INTEL', U) > 0) or (Pos('UHD GRAPHICS', U) > 0) or (Pos('HD GRAPHICS', U) > 0) or
     (Pos('VEGA', U) > 0) or (Pos('RADEON(TM) GRAPHICS', U) > 0) then
  begin
    Result := 2;
    Exit;
  end;

  // GPU desconhecida/não mapeada -> deixa o usuário escolher com segurança
  Result := -1;
end;

// Devolve a URL, o tamanho estimado (MB) e o rótulo do modelo GGUF
// correspondente à opção escolhida na tela de GPU (índices 0..4).
function GetModelInfo(Index: Integer; var Url: String; var SizeMB: Int64; var Label_: String): Boolean;
const
  BaseUrl = 'https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/';
begin
  Result := True;
  case Index of
    0: begin // GPU forte (RTX 3060 ou superior, 8GB+ VRAM)
         Url := BaseUrl + 'qwen2.5-7b-instruct-q8_0.gguf';
         SizeMB := 8100;
         Label_ := 'Qwen2.5-7B-Instruct-Q8_0 (alta qualidade, ~8.1 GB)';
       end;
    1: begin // GPU mediana (GTX 1050-1080 / RX 580, 4-8GB VRAM)
         Url := BaseUrl + 'qwen2.5-7b-instruct-q4_k_m.gguf';
         SizeMB := 4700;
         Label_ := 'Qwen2.5-7B-Instruct-Q4_K_M (equilibrado, ~4.7 GB)';
       end;
    2: begin // GPU fraca/integrada
         Url := BaseUrl + 'qwen2.5-7b-instruct-q2_k.gguf';
         SizeMB := 3100;
         Label_ := 'Qwen2.5-7B-Instruct-Q2_K (mais leve, ~3.1 GB)';
       end;
    3: begin // apenas CPU
         Url := BaseUrl + 'qwen2.5-7b-instruct-q2_k.gguf';
         SizeMB := 3100;
         Label_ := 'Qwen2.5-7B-Instruct-Q2_K (recomendado para CPU, ~3.1 GB)';
       end;
    4: begin // "Não sei" -> opção mais segura/equilibrada
         Url := BaseUrl + 'qwen2.5-7b-instruct-q4_k_m.gguf';
         SizeMB := 4700;
         Label_ := 'Qwen2.5-7B-Instruct-Q4_K_M (opção segura, ~4.7 GB)';
       end;
  else
    Result := False;
  end;
end;

// Extrai um valor de um JSON simples e "achatado" (sem objetos aninhados),
// que é exatamente o formato que o nosso DownloadFile.ps1 escreve.
// Não é um parser JSON de verdade - só serve para esse caso controlado.
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

// Devolve o índice selecionado na lista de opções de GPU (0..4).
function GetSelectedGpuIndex(): Integer;
var
  I: Integer;
begin
  Result := 4; // fallback de segurança: "Não sei"
  for I := 0 to GpuPage.CheckListBox.Items.Count - 1 do
    if GpuPage.Values[I] then
    begin
      Result := I;
      Break;
    end;
end;


// ============================================================================
// VERIFICAÇÕES (espaço em disco / WebView2)
// ============================================================================

function HasEnoughDiskSpace(const Drive: String; const RequiredMB: Int64): Boolean;
var
  FreeMB: Int64;
begin
  Result := GetSpaceOnDisk64(Drive, True, FreeMB) and (FreeMB >= RequiredMB);
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

// Baixa um arquivo pequeno de forma simples e síncrona (sem barra de
// progresso, sem retomada - usado só para o instalador do WebView2, que
// tem ~1.5 MB e não justifica a complexidade do BITS).
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


// ============================================================================
// DOWNLOAD DO MODELO (com barra de progresso e retomada via BITS)
// ============================================================================

procedure DownloadModelWithProgress;
var
  ScriptPath, StatusPath, DestPath, Cmd: String;
  StatusJson, State, Msg: String;
  Percent: Integer;
  ResultCode: Integer;
  Elapsed: Integer;
const
  MaxWaitSeconds = 4 * 60 * 60; // 4 horas - trava de segurança
begin
  ExtractTemporaryFile('DownloadFile.ps1');
  ScriptPath := ExpandConstant('{tmp}\DownloadFile.ps1');
  StatusPath := ExpandConstant('{tmp}\hermes_download_status.json');
  LogFilePath := ExpandConstant('{app}\data\logs\installer_download.log');
  DestPath := ExpandConstant('{app}\models\hermes-core.gguf');

  ForceDirectories(ExpandConstant('{app}\models'));
  ForceDirectories(ExpandConstant('{app}\data\logs'));
  DeleteFile(StatusPath);

  Cmd := Format(
    '-NoProfile -ExecutionPolicy Bypass -File "%s" -Url "%s" -Destination "%s" -StatusFile "%s" -LogFile "%s"',
    [ScriptPath, SelectedModelUrl, DestPath, StatusPath, LogFilePath]);

  // Dispara o download em segundo plano (ewNoWait) - o próprio script
  // PowerShell fica rodando e atualizando o arquivo de status até terminar.
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '',
              SW_HIDE, ewNoWait, ResultCode) then
  begin
    MsgBox('Não foi possível iniciar o download do modelo de IA.', mbError, MB_OK);
    Exit;
  end;

  DownloadPage.SetText('Iniciando download...', '');
  DownloadPage.SetProgress(0, 100);
  DownloadPage.Show;
  try
    State := '';
    Elapsed := 0;
    repeat
      Sleep(1000); // o Sleep do Inno processa a fila de mensagens - a UI continua responsiva
      Inc(Elapsed);

      if LoadStringFromFile(StatusPath, StatusJson) then
      begin
        State := ExtractJsonValue(StatusJson, 'state');
        Percent := StrToIntDef(ExtractJsonValue(StatusJson, 'percent'), 0);
        Msg := ExtractJsonValue(StatusJson, 'message');

        DownloadPage.SetProgress(Percent, 100);
        DownloadPage.SetText('Baixando o modelo de IA... (' + IntToStr(Percent) + '%)', Msg);
      end;
    until (State = 'done') or (State = 'error') or (Elapsed >= MaxWaitSeconds);

    if State = 'error' then
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
    DownloadPage.Hide;
  end;
end;


// ============================================================================
// EVENTOS DO WIZARD
// ============================================================================

procedure InitializeWizard;
var
  DetectedIndex: Integer;
begin
  // --- Tela de seleção de GPU ---
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

  // --- Tela "baixar agora ou depois?" ---
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
  DownloadCheckBox.Caption := 'Baixar o modelo agora (recomendado)';
  DownloadCheckBox.Checked := True;

  SkipInfoLabel := TNewStaticText.Create(DownloadOptPage);
  SkipInfoLabel.Parent := DownloadOptPage.Surface;
  SkipInfoLabel.Left := 0;
  SkipInfoLabel.Top := DownloadCheckBox.Top + 30;
  SkipInfoLabel.Width := DownloadOptPage.SurfaceWidth;
  SkipInfoLabel.WordWrap := True;
  SkipInfoLabel.Caption :=
    'Se preferir pular esta etapa (ex.: internet lenta), o Hermes AI será instalado ' +
    'sem o modelo. Depois, basta baixar o arquivo .gguf e colocá-lo em ' +
    '"models\hermes-core.gguf" dentro da pasta de instalação.';

  // --- Tela de progresso do download (mostrada/escondida durante a instalação) ---
  DownloadPage := CreateOutputProgressPage(
    'Baixando o modelo de IA',
    'Isso pode levar alguns minutos, dependendo da sua internet.');
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
    if not DownloadCheckBox.Checked then
      WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption +
        #13#10#13#10 +
        'Lembre-se: você optou por não baixar o modelo de IA agora.' + #13#10 +
        'Baixe manualmente e coloque o arquivo em:' + #13#10 +
        ExpandConstant('{app}') + '\models\hermes-core.gguf' + #13#10#13#10 +
        'Modelo recomendado: ' + SelectedModelUrl;
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
    RequiredMB := SelectedModelSizeMB + 500; // margem de segurança
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
      DownloadModelWithProgress;
  end;
end;