#!/usr/bin/env bash
#
# Publica el Ollama de esta máquina para que la aplicación desplegada pueda
# usarlo. Levanta dos cosas:
#
#   1. El proxy autenticado (scripts/ollama_proxy.py), que exige un token y
#      solo deja pasar los endpoints que la aplicación necesita.
#   2. Un túnel de Cloudflare, que da una URL pública sin tocar el router.
#
# Uso:
#     export OLLAMA_TOKEN="tu-token"      # si no, se genera uno
#     ./scripts/exponer_ollama.sh
#
# Deja la terminal abierta: al cerrarla se cae el túnel.

set -euo pipefail

PUERTO="${PROXY_PORT:-11435}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Intérprete: se prefiere el entorno virtual del proyecto
PYTHON="$RAIZ/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

CLOUDFLARED="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"

if [ ! -x "$CLOUDFLARED" ]; then
    echo "❌ Falta cloudflared. Instálalo con:"
    echo "   curl -sL -o /tmp/cf.tgz https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"
    echo "   tar xzf /tmp/cf.tgz -C /tmp && mkdir -p ~/.local/bin && mv /tmp/cloudflared ~/.local/bin/"
    exit 1
fi

if ! curl -s -o /dev/null --max-time 3 http://localhost:11434/api/tags; then
    echo "❌ Ollama no responde en http://localhost:11434"
    echo "   Abre la aplicación Ollama y vuelve a intentarlo."
    exit 1
fi

# Si el puerto ya está ocupado, el proxy nuevo muere al arrancar y el túnel
# acabaría apuntando a un proceso viejo, con otro token: las credenciales que
# imprime este script no servirían.
if OCUPANTE="$(lsof -ti:"$PUERTO" 2>/dev/null)" && [ -n "$OCUPANTE" ]; then
    echo "❌ El puerto $PUERTO ya está ocupado por el proceso $OCUPANTE."
    echo
    echo "   Seguramente quedó un proxy de una ejecución anterior. Ciérralo con:"
    echo "       kill $OCUPANTE"
    echo
    echo "   O usa otro puerto:"
    echo "       PROXY_PORT=11436 $0"
    exit 1
fi

if [ -z "${OLLAMA_TOKEN:-}" ]; then
    OLLAMA_TOKEN="$("$PYTHON" -c 'import secrets; print(secrets.token_hex(32))')"
    export OLLAMA_TOKEN
    echo "🔑 Token generado (guárdalo, es el que va en la variable OLLAMA_TOKEN):"
    echo "   $OLLAMA_TOKEN"
    echo
fi

REGISTRO="$(mktemp -t tunel-ollama)"

limpiar() {
    echo
    echo "Cerrando proxy y túnel..."
    # shellcheck disable=SC2046
    kill $(jobs -p) 2>/dev/null || true
}
trap limpiar EXIT INT TERM

echo "▶️  Arrancando el proxy autenticado en el puerto $PUERTO..."
"$PYTHON" "$RAIZ/scripts/ollama_proxy.py" &
PROXY_PID=$!

# El proxy tiene que responder con el token recién generado antes de seguir.
# Sin esta comprobación, un fallo al arrancar pasaba desapercibido y el script
# terminaba anunciando una URL y un token que no funcionaban.
PROXY_LISTO=""
for _ in $(seq 1 15); do
    if ! kill -0 "$PROXY_PID" 2>/dev/null; then
        echo "❌ El proxy se cerró nada más arrancar. Revisa el error de arriba."
        exit 1
    fi
    CODIGO="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 \
        -H "Authorization: Bearer $OLLAMA_TOKEN" \
        "http://localhost:$PUERTO/api/tags" || true)"
    if [ "$CODIGO" = "200" ]; then
        PROXY_LISTO="si"
        break
    fi
    sleep 1
done

if [ -z "$PROXY_LISTO" ]; then
    echo "❌ El proxy no respondió correctamente en el puerto $PUERTO."
    echo "   Si otro proceso lo está usando, ciérralo o prueba con PROXY_PORT=11436."
    exit 1
fi

echo "✅ Proxy respondiendo con el token generado."
echo "▶️  Abriendo el túnel de Cloudflare..."
"$CLOUDFLARED" tunnel --url "http://localhost:$PUERTO" --no-autoupdate > "$REGISTRO" 2>&1 &

# La URL tarda unos segundos en aparecer en el registro del túnel
URL=""
for _ in $(seq 1 30); do
    URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$REGISTRO" | head -1 || true)"
    [ -n "$URL" ] && break
    sleep 1
done

if [ -z "$URL" ]; then
    echo "❌ El túnel no entregó una URL. Registro completo:"
    cat "$REGISTRO"
    exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════"
echo "✅ Ollama publicado en:"
echo "   $URL"
echo
echo "Configura estas variables de entorno en el proyecto desplegado:"
echo
echo "   OLLAMA_URL    = $URL"
echo "   OLLAMA_TOKEN  = $OLLAMA_TOKEN"
echo "   OLLAMA_MODEL  = llama3.1"
echo
echo "⚠️  La URL cambia cada vez que se reinicia este script, así que habrá"
echo "    que actualizar OLLAMA_URL y volver a desplegar."
echo "⚠️  Mientras esta terminal esté cerrada, la aplicación desplegada"
echo "    seguirá funcionando, pero sin reescritura con IA."
echo "════════════════════════════════════════════════════════════════"
echo
echo "Ctrl+C para detener."

wait
