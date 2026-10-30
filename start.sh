#!/usr/bin/env bash
# Divisao de Contas - inicializacao para macOS e Linux.
# Uso: ./start.sh [iniciar|parar|reiniciar|status]   (sem argumento abre o menu)
set -u
cd "$(dirname "$0")" || exit 1

PORT="${DIVISAO_PORT:-8000}"
URL="http://localhost:${PORT}"
SCRIPT_NAME="$(basename "$0")"
SERVER_PID=""

# ---- Rotinas ----

is_running() {
  # Procura o processo Python que escuta na porta.
  SERVER_PID=""
  local pids pid name
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)"
  elif command -v ss >/dev/null 2>&1; then
    pids="$(ss -ltnpH "sport = :$PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2)"
  elif command -v fuser >/dev/null 2>&1; then
    pids="$(fuser -n tcp "$PORT" 2>/dev/null)"
  else
    pids=""
  fi
  for pid in $pids; do
    name="$(ps -p "$pid" -o comm= 2>/dev/null)"
    case "$(basename "${name:-}")" in
      python*|Python*|uvicorn*) SERVER_PID="$pid"; return 0 ;;
    esac
  done
  return 0
}

open_browser() {
  if command -v open >/dev/null 2>&1 && [ "$(uname)" = "Darwin" ]; then
    open "$URL" >/dev/null 2>&1 &
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
  fi
}

find_python() {
  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

prepare() {
  if [ ! -x ".venv/bin/python" ] || [ ! -f ".venv/bin/activate" ]; then
    local py
    if ! py="$(find_python)"; then
      echo "Python 3.12 ou superior e necessario."
      return 1
    fi
    echo "Criando o ambiente Python em .venv..."
    if ! "$py" -m venv .venv; then
      echo "Nao foi possivel criar o ambiente Python."
      return 1
    fi
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
  # Reinstala as dependencias quando o requirements.txt mudou ou a ultima instalacao nao terminou.
  # A copia em .venv/requirements.installed so e gravada depois de uma instalacao bem-sucedida.
  if ! cmp -s backend/requirements.txt .venv/requirements.installed; then
    echo "Instalando as dependencias do backend..."
    python -m pip install --upgrade pip
    if ! python -m pip install -r backend/requirements.txt; then
      echo "Falha ao instalar as dependencias. Verifique a conexao e execute de novo."
      echo "Se o erro continuar, apague a pasta .venv para recriar o ambiente."
      return 1
    fi
    cp backend/requirements.txt .venv/requirements.installed
  fi
  if [ ! -f "frontend/dist/index.html" ]; then
    if ! command -v npm >/dev/null 2>&1; then
      echo "Node.js 20 ou superior e necessario para compilar a interface."
      return 1
    fi
    (cd frontend && npm install && npm run build) || return 1
  fi
  return 0
}

stop() {
  is_running
  if [ -z "$SERVER_PID" ]; then
    echo "O servidor nao esta em execucao."
    return 0
  fi
  echo "Parando o servidor - PID $SERVER_PID..."
  kill "$SERVER_PID" 2>/dev/null
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    is_running
    if [ -z "$SERVER_PID" ]; then
      echo "Servidor parado."
      return 0
    fi
    [ "$i" -eq 5 ] && kill -9 "$SERVER_PID" 2>/dev/null
    sleep 1
  done
  echo "Nao foi possivel parar o servidor na porta $PORT."
  return 1
}

run() {
  echo
  echo "Servidor em $URL"
  echo "Para parar: feche este terminal, tecle Ctrl+C ou execute \"./$SCRIPT_NAME parar\"."
  echo
  exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "$PORT"
}

do_start() {
  is_running
  if [ -n "$SERVER_PID" ]; then
    echo "O servidor ja esta em execucao - PID $SERVER_PID. Abrindo $URL"
    open_browser
    exit 0
  fi
  prepare || exit 1
  # Abre o navegador assim que o servidor estiver pronto.
  ( sleep 2; open_browser ) &
  run
}

do_restart() {
  stop || exit 1
  prepare || exit 1
  run
}

status_once() {
  is_running
  if [ -n "$SERVER_PID" ]; then
    echo "Servidor em execucao - PID $SERVER_PID - $URL"
    exit 0
  fi
  echo "Servidor parado."
  exit 1
}

menu() {
  # Na primeira exibicao inicia sozinho em 10 segundos.
  local timeout_opt="-t 10" choice
  while true; do
    is_running
    echo
    echo " ===== Divisao de Contas ====="
    if [ -n "$SERVER_PID" ]; then
      echo " Servidor: EM EXECUCAO - PID $SERVER_PID - $URL"
    else
      echo " Servidor: PARADO"
    fi
    echo
    echo "  [1] Iniciar"
    echo "  [2] Reiniciar"
    echo "  [3] Parar"
    echo "  [4] Status"
    echo "  [0] Sair"
    echo
    choice=""
    # shellcheck disable=SC2086
    read -r -n 1 $timeout_opt -p "Escolha uma opcao: " choice || choice="1"
    echo
    timeout_opt=""
    case "$choice" in
      1) do_start ;;
      2) do_restart ;;
      3) stop ;;
      4) ;;
      0) exit 0 ;;
      *) ;;
    esac
  done
}

case "${1:-}" in
  iniciar|start) do_start ;;
  parar|stop) stop; exit $? ;;
  reiniciar|restart) do_restart ;;
  status) status_once ;;
  "") menu ;;
  *)
    echo "Uso: $SCRIPT_NAME [iniciar|parar|reiniciar|status]"
    exit 1
    ;;
esac
