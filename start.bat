@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Divisao de Contas
if "%DIVISAO_PORT%"=="" (set "PORT=8000") else (set "PORT=%DIVISAO_PORT%")
set "URL=http://localhost:%PORT%"

rem Uso: start.bat [iniciar^|parar^|reiniciar^|status]   (sem argumento abre o menu)
set "ACTION=%~1"
if /i "%ACTION%"=="iniciar" goto start
if /i "%ACTION%"=="start" goto start
if /i "%ACTION%"=="parar" goto stop_once
if /i "%ACTION%"=="stop" goto stop_once
if /i "%ACTION%"=="reiniciar" goto restart
if /i "%ACTION%"=="restart" goto restart
if /i "%ACTION%"=="status" goto status_once
if not "%ACTION%"=="" (
  echo Uso: %~nx0 [iniciar^|parar^|reiniciar^|status]
  exit /b 1
)

rem ---- Menu: na primeira exibicao inicia sozinho em 10 segundos ----
set "WAIT=/t 10 /d 1"
:menu
call :is_running
echo.
echo  ===== Divisao de Contas =====
if defined SERVER_PID (
  echo  Servidor: EM EXECUCAO - PID %SERVER_PID% - %URL%
) else (
  echo  Servidor: PARADO
)
echo.
echo   [1] Iniciar
echo   [2] Reiniciar
echo   [3] Parar
echo   [4] Status
echo   [0] Sair
echo.
choice /c 12340 /n %WAIT% /m "Escolha uma opcao: "
set "CHOICE_RESULT=%errorlevel%"
set "WAIT="
if "%CHOICE_RESULT%"=="5" exit /b 0
if "%CHOICE_RESULT%"=="4" goto menu
if "%CHOICE_RESULT%"=="3" (
  call :stop
  goto menu
)
if "%CHOICE_RESULT%"=="2" goto restart
goto start

:status_once
call :is_running
if defined SERVER_PID (
  echo Servidor em execucao - PID %SERVER_PID% - %URL%
  exit /b 0
)
echo Servidor parado.
exit /b 1

:stop_once
call :stop
exit /b %errorlevel%

:start
call :is_running
if defined SERVER_PID (
  echo O servidor ja esta em execucao - PID %SERVER_PID%. Abrindo %URL%
  start "" %URL%
  timeout /t 3 >nul
  exit /b 0
)
call :prepare || exit /b 1
start "" %URL%
goto run

:restart
call :stop || exit /b 1
call :prepare || exit /b 1
goto run

:run
echo.
echo Servidor em %URL%
echo Para parar: feche esta janela, tecle Ctrl+C ou execute "%~nx0 parar".
echo.
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port %PORT%
exit /b %errorlevel%

rem ---- Rotinas ----

:prepare
set "VENV_OK=1"
if not exist ".venv\Scripts\python.exe" set "VENV_OK="
if not exist ".venv\Scripts\activate.bat" set "VENV_OK="
if not defined VENV_OK (
  echo Criando o ambiente Python em .venv...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Nao foi possivel criar o ambiente Python. Instale o Python 3.12 ou superior.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
rem Reinstala as dependencias quando o requirements.txt mudou ou a ultima instalacao nao terminou.
rem A copia em .venv\requirements.installed so e gravada depois de uma instalacao bem-sucedida.
fc /b "backend\requirements.txt" ".venv\requirements.installed" >nul 2>&1
if errorlevel 1 (
  echo Instalando as dependencias do backend...
  python -m pip install --upgrade pip
  python -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo Falha ao instalar as dependencias. Verifique a conexao e execute de novo.
    echo Se o erro continuar, apague a pasta .venv para recriar o ambiente.
    pause
    exit /b 1
  )
  copy /y "backend\requirements.txt" ".venv\requirements.installed" >nul
)
if not exist "frontend\dist\index.html" (
  where npm.cmd >nul 2>&1
  if errorlevel 1 (
    echo Node.js 20 ou superior e necessario para compilar a interface.
    pause
    exit /b 1
  )
  pushd frontend
  call npm.cmd install
  if errorlevel 1 exit /b 1
  call npm.cmd run build
  if errorlevel 1 exit /b 1
  popd
)
exit /b 0

:stop
call :is_running
if not defined SERVER_PID (
  echo O servidor nao esta em execucao.
  exit /b 0
)
echo Parando o servidor - PID %SERVER_PID%...
taskkill /PID %SERVER_PID% /T /F >nul 2>&1
for /l %%i in (1,1,10) do (
  call :is_running
  if not defined SERVER_PID (
    echo Servidor parado.
    exit /b 0
  )
  timeout /t 1 /nobreak >nul
)
echo Nao foi possivel parar o servidor na porta %PORT%.
exit /b 1

:is_running
rem Procura o processo Python que escuta na porta (independe do idioma do Windows).
set "SERVER_PID="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$ids=@(Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue).OwningProcess; foreach($i in $ids){ if((Get-Process -Id $i -ErrorAction SilentlyContinue).ProcessName -like 'python*'){ $i; break } }"`) do set "SERVER_PID=%%p"
exit /b 0
