#!/bin/bash
# Corre el worker de AI Auto Apply en este Mac contra la base de datos de Vercel.
# Pide la DATABASE_URL sin mostrarla ni guardarla. NO activa el envío real.
set -e
cd "$(dirname "$0")/.."
read -r -s -p "Pega la DATABASE_URL de Vercel y pulsa Enter (no se ve): " DATABASE_URL
echo
# Limpia lo típico al copiar: prefijo DATABASE_URL=, comillas, espacios y restos de "pegado" de la terminal.
DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed -e $'s/\x1b\\[20[01]~//g' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
  -e 's/^[A-Za-z_]*=//' -e "s/^[\"']//" -e "s/[\"']$//")"
case "$DATABASE_URL" in
  postgres://*|postgresql://*) ;;
  *) echo "Eso no parece una URL de Postgres (debe empezar por postgres:// o postgresql://)."
     echo "Largo recibido: ${#DATABASE_URL} caracteres; empieza por: '${DATABASE_URL:0:12}'"; exit 1;;
esac
case "$DATABASE_URL" in postgres://*) DATABASE_URL="postgresql://${DATABASE_URL#postgres://}";; esac
echo "URL recibida: ${#DATABASE_URL} caracteres, host: $(printf '%s' "$DATABASE_URL" | sed -E 's#^[^@]*@([^/:?]+).*#\1#')"
export DATABASE_URL
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:14b}"
unset AUTOAPPLY_ENABLE_SUBMIT
echo "Worker iniciado (envío real: deshabilitado). Ctrl+C para detenerlo."
exec .venv/bin/python -m autoapply.worker
