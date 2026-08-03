#!/usr/bin/env bash
set -euo pipefail

# Opciones estrictas de bash para tolerancia a fallos:
# -e: Detiene el script si cualquier comando falla.
# -u: Falla si se intenta utilizar una variable no definida.
# -o pipefail: El código de salida de un pipeline es el del último comando que falló.

# Colores para la salida
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Modo desinstalación
if [ "${1:-}" = "--uninstall" ]; then
    echo_info "Desinstalando CelarPass CLI..."
    UNINSTALL_BIN="$HOME/.local/bin/celarpass-cli"
    UNINSTALL_DIR="$HOME/.local/share/celarpass-cli"
    if [ -f "$UNINSTALL_BIN" ]; then
        rm -f "$UNINSTALL_BIN"
        echo_info "Ejecutable eliminado de $UNINSTALL_BIN."
    fi
    if [ -d "$UNINSTALL_DIR" ]; then
        rm -rf "$UNINSTALL_DIR"
        echo_info "Directorio de datos eliminado de $UNINSTALL_DIR."
    fi
    echo_info "✅ Desinstalación completada exitosamente."
    exit 0
fi

# ==========================================
# CONFIGURACIÓN DE INSTALACIÓN
# ==========================================
# Versiones fijadas para evitar ataques de cadena de suministro en ramas mutables (ej. main).
CLI_VERSION="v1.0.4"
# CORE_VERSION usa el hash completo del commit del repositorio celarpass_core.
CORE_VERSION="db062ca25df073b6f0b97770d802ff6e0aa43338"

# Ubicación del ejecutable a nivel de usuario (evita requerir sudo)
BIN_LINK="$HOME/.local/bin/celarpass-cli"

# Validar dependencias esenciales
for cmd in python3 git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo_err "Dependencia faltante: '$cmd'. Por favor, instálalo antes de continuar."
    fi
done

# Detectar gestor de paquetes para dar instrucciones precisas según la distro.
PKG_HINT=""
if command -v apt >/dev/null 2>&1; then
    PKG_HINT="sudo apt install python3-venv python3-pip"
elif command -v dnf >/dev/null 2>&1; then
    PKG_HINT="sudo dnf install python3-pip python3-virtualenv"
elif command -v yum >/dev/null 2>&1; then
    PKG_HINT="sudo yum install python3-pip python3-virtualenv"
elif command -v zypper >/dev/null 2>&1; then
    PKG_HINT="sudo zypper install python3-pip python3-virtualenv"
elif command -v pacman >/dev/null 2>&1; then
    PKG_HINT="sudo pacman -S python-pip python-virtualenv"
elif command -v apk >/dev/null 2>&1; then
    PKG_HINT="sudo apk add python3-dev py3-pip py3-virtualenv"
fi

if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
    if [ -n "$PKG_HINT" ]; then
        echo_err "El módulo 'ensurepip' (venv) de Python no está disponible.\nInstálalo con: $PKG_HINT"
    else
        echo_err "El módulo 'ensurepip' (venv) de Python no está disponible.\nInstala el paquete de entorno virtual correspondiente a tu distribución."
    fi
fi

# Validar versión mínima de Python (3.8+)
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 8) else 0)')
if [ "$PY_OK" != "1" ]; then
    PY_VER=$(python3 -c 'import platform; print(platform.python_version())')
    echo_err "Se requiere Python 3.8 o superior (detectado: $PY_VER). Actualiza Python antes de continuar."
fi

# ==========================================
# DETERMINAR MODO DE EJECUCIÓN
# ==========================================
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

if [ -f "$CURRENT_DIR/celarpass_cli.py" ] && [ -d "$CURRENT_DIR/celarpass_core" ]; then
    echo_info "Ejecutando en Modo Local (Repositorio clonado)..."
    INSTALL_DIR="$CURRENT_DIR"
    CLI_SCRIPT="$INSTALL_DIR/celarpass_cli.py"
    VENV_DIR="$INSTALL_DIR/.venv"
    CORE_REPO_PATH="$INSTALL_DIR/celarpass_core"

    chmod +x "$CLI_SCRIPT"
else
    echo_info "Ejecutando en Modo Standalone (Instalación en ~/.local/share)..."
    INSTALL_DIR="$HOME/.local/share/celarpass-cli"
    CLI_SCRIPT="$INSTALL_DIR/celarpass_cli.py"
    REQ_SCRIPT="$INSTALL_DIR/requirements-cli.txt"
    VENV_DIR="$INSTALL_DIR/.venv"
    CORE_REPO_PATH="$INSTALL_DIR/celarpass_core_repo"
    
    mkdir -p "$INSTALL_DIR"
    
    echo_info "Descargando celarpass_cli.py y requirements-cli.txt (versión: $CLI_VERSION)..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/${CLI_VERSION}/celarpass_cli.py" -o "$CLI_SCRIPT" || echo_err "Fallo al descargar celarpass_cli.py."
        curl -fsSL "https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/${CLI_VERSION}/requirements-cli.txt" -o "$REQ_SCRIPT" || echo_err "Fallo al descargar requirements-cli.txt."
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$CLI_SCRIPT" "https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/${CLI_VERSION}/celarpass_cli.py" || echo_err "Fallo al descargar celarpass_cli.py."
        wget -qO "$REQ_SCRIPT" "https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/${CLI_VERSION}/requirements-cli.txt" || echo_err "Fallo al descargar requirements-cli.txt."
    else
        echo_err "Necesitas tener instalado 'curl' o 'wget' para descargar los archivos."
    fi

    # Verificación de integridad del script descargado (SHA256 para la versión v1.0.4)
    EXPECTED_SHA="580db83f59f17564b64b486bdca0fb136ee99081bdcad1dcb3fafdbe88dd6439"
    ACTUAL_SHA=$(sha256sum "$CLI_SCRIPT" | cut -d' ' -f1)
    if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
        rm -f "$CLI_SCRIPT" "$REQ_SCRIPT"
        echo_err "Verificación de integridad fallida. El archivo descargado no coincide con el checksum esperado. Posible compromiso en la red o repositorio."
    fi

    chmod +x "$CLI_SCRIPT"
    
    if [ ! -d "$CORE_REPO_PATH" ]; then
        echo_info "Clonando repositorio criptográfico base (versión: $CORE_VERSION)..."
        git clone -q "https://github.com/Eduardo-ci/celarpass_core.git" "$CORE_REPO_PATH"
        git -C "$CORE_REPO_PATH" checkout -q "$CORE_VERSION"
    else
        echo_info "Actualizando repositorio criptográfico base (versión: $CORE_VERSION)..."
        git -C "$CORE_REPO_PATH" fetch -q origin
        git -C "$CORE_REPO_PATH" checkout -q "$CORE_VERSION"
    fi

    # Verificación de integridad del repositorio criptográfico base
    ACTUAL_CORE_COMMIT=$(git -C "$CORE_REPO_PATH" rev-parse HEAD)
    if [ "$ACTUAL_CORE_COMMIT" != "$CORE_VERSION" ]; then
        rm -rf "$CORE_REPO_PATH"
        echo_err "Verificación de integridad fallida para celarpass_core. Commit esperado: $CORE_VERSION, obtenido: $ACTUAL_CORE_COMMIT. Posible compromiso del repositorio."
    fi
fi

# Detectar paquete celarpass_core para pip
PIP_INSTALL_TARGET=""
if [ -f "$CORE_REPO_PATH/setup.py" ] || [ -f "$CORE_REPO_PATH/pyproject.toml" ]; then
    PIP_INSTALL_TARGET="$CORE_REPO_PATH"
elif [ -f "$CORE_REPO_PATH/celarpass_core/setup.py" ] || [ -f "$CORE_REPO_PATH/celarpass_core/pyproject.toml" ]; then
    PIP_INSTALL_TARGET="$CORE_REPO_PATH/celarpass_core"
else
    if [ "$CURRENT_DIR" = "$INSTALL_DIR" ]; then
        echo_warn "No se encontró 'setup.py' ni 'pyproject.toml' en modo local. Se omitirá la instalación de celarpass_core con pip."
    else
        echo_err "No se encontró 'setup.py' ni 'pyproject.toml' en '$CORE_REPO_PATH'. No es posible instalar celarpass_core como paquete de Python."
    fi
fi

echo_info "Preparando CelarPass CLI en $INSTALL_DIR..."

# Detectar y preparar entorno virtual
VENV_IS_NEW=0
if [ ! -d "$VENV_DIR" ]; then
    VENV_IS_NEW=1
    echo_info "Creando entorno virtual aislado para dependencias..."
    python3 -m venv "$VENV_DIR"
else
    echo_info "Entorno virtual (.venv) ya existente."
fi

PIP_CMD=("$VENV_DIR/bin/pip")

echo_info "Instalando/verificando dependencias requeridas..."
if [ -f "$INSTALL_DIR/requirements-cli.txt" ]; then
    "${PIP_CMD[@]}" install --quiet --no-cache-dir --require-hashes -r "$INSTALL_DIR/requirements-cli.txt"
elif [ -f "$INSTALL_DIR/requirements.txt" ]; then
    "${PIP_CMD[@]}" install --quiet --no-cache-dir -r "$INSTALL_DIR/requirements.txt"
else
    echo_err "No se encontró requirements-cli.txt ni requirements.txt. Abortando instalación."
fi

if [ -n "$PIP_INSTALL_TARGET" ] && [ -d "$PIP_INSTALL_TARGET" ]; then
    echo_info "Instalando/actualizando paquete celarpass_core en el entorno virtual..."
    "${PIP_CMD[@]}" install --quiet --no-cache-dir --force-reinstall --no-deps "$PIP_INSTALL_TARGET"
fi

# Crear el acceso global (wrapper) con permisos restringidos al propietario (700)
BIN_DIR="$(dirname "$BIN_LINK")"
if [ ! -d "$BIN_DIR" ]; then
    mkdir -p "$BIN_DIR" || echo_err "No se pudo crear el directorio '$BIN_DIR'."
fi
if [ ! -w "$BIN_DIR" ]; then
    echo_err "'$BIN_DIR' no es escribible. No se puede instalar el ejecutable global."
fi

echo_info "Creando ejecutable global en $BIN_LINK..."
cat > "$BIN_LINK" << EOF
#!/usr/bin/env bash
# Wrapper generado automáticamente para CelarPass CLI
set -euo pipefail
source "$VENV_DIR/bin/activate"
exec python3 "$CLI_SCRIPT" "\$@"
EOF

chmod 700 "$BIN_LINK"

echo_info "✅ CelarPass CLI instalado exitosamente."

# Verificar si ~/.local/bin está en el PATH del usuario
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo_warn "Atención: '$BIN_DIR' no se encuentra en tu variable \$PATH."
    echo_warn "Para ejecutar 'celarpass-cli' directamente desde cualquier lugar, añade lo siguiente a tu ~/.bashrc o ~/.zshrc:"
    echo -e "  ${YELLOW}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
else
    echo_info "Ahora puedes usar la herramienta globalmente en tu terminal:"
    echo -e "  ${GREEN}celarpass-cli --help${NC}"
fi
