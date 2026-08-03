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

# Permisos de administrador ya no son obligatorios en todo el script.
# La instalación se realizará en el espacio del usuario (~/.local).
# Si se requieren dependencias del sistema, se solicitará instalarlas manualmente.

# ==========================================
# CONFIGURACIÓN DE INSTALACIÓN
# ==========================================
# Versiones fijadas para evitar ataques de cadena de suministro en ramas mutables (ej. main).
CLI_VERSION="v1.0.4"
# CORE_VERSION usa el hash completo del commit porque el repositorio
# celarpass_core aún no tiene tags de release. Un hash de commit es
# inmutable y más seguro que apuntar a una rama.
CORE_VERSION="025db8e9f88251accfc9a09f64483c216fc1c080"

# Ubicación del ejecutable a nivel de usuario (evita requerir sudo)
BIN_LINK="$HOME/.local/bin/celarpass-cli"

# Validar dependencias esenciales
for cmd in python3 git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo_err "Dependencia faltante: '$cmd'. Por favor, instálalo antes de continuar."
    fi
done

# Detectar gestor de paquetes para dar instrucciones precisas según la distro.
# Esto evita asumir que todo el mundo usa apt (Debian/Ubuntu); en Fedora/RHEL
# es dnf/yum, en openSUSE es zypper, en Arch es pacman, y en Alpine es apk.
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
        echo_err "El módulo 'ensurepip' (venv) de Python no está disponible.\nInstala el paquete de entorno virtual correspondiente a tu distribución (busca 'python3-venv', 'python-virtualenv' o similar en tu gestor de paquetes)."
    fi
fi

# Validar versión mínima de Python (3.8+). Distros LTS antiguas (Debian 10,
# CentOS 7/8, Ubuntu 18.04) traen Python 3.6/3.7 por defecto, donde algunas
# dependencias (cryptography reciente, etc.) ya no instalan correctamente.
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 8) else 0)')
if [ "$PY_OK" != "1" ]; then
    PY_VER=$(python3 -c 'import platform; print(platform.python_version())')
    echo_err "Se requiere Python 3.8 o superior (detectado: $PY_VER). Actualiza Python antes de continuar."
fi

# ==========================================
# DETERMINAR MODO DE EJECUCIÓN
# ==========================================
# Local: Instalación orientada a desarrollo (se asume repositorio clonado).
# Standalone: Instalación a nivel de usuario (descarga e instala en ~/.local/share).
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

if [ -f "$CURRENT_DIR/celarpass_cli.py" ] && [ -d "$CURRENT_DIR/celarpass_core" ]; then
    echo_info "Ejecutando en Modo Local (Repositorio clonado)..."
    INSTALL_DIR="$CURRENT_DIR"
    CLI_SCRIPT="$INSTALL_DIR/celarpass_cli.py"
    VENV_DIR="$INSTALL_DIR/.venv"
    # CORE_REPO_PATH apunta a la carpeta clonada de celarpass_core tal cual
    # está en disco. Puede o no tener anidamiento (celarpass_core/celarpass_core/);
    # eso se resuelve más abajo de forma común para ambos modos.
    CORE_REPO_PATH="$INSTALL_DIR/celarpass_core"

    chmod +x "$CLI_SCRIPT"
else
    echo_info "Ejecutando en Modo Standalone (Instalación en ~/.local/share)..."
    INSTALL_DIR="$HOME/.local/share/celarpass-cli"
    CLI_SCRIPT="$INSTALL_DIR/celarpass_cli.py"
    VENV_DIR="$INSTALL_DIR/.venv"
    CORE_REPO_PATH="$INSTALL_DIR/celarpass_core_repo"
    
    mkdir -p "$INSTALL_DIR"
    
    echo_info "Descargando celarpass_cli.py (versión: $CLI_VERSION)..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/${CLI_VERSION}/celarpass_cli.py" -o "$CLI_SCRIPT" || echo_err "Fallo al descargar celarpass_cli.py."
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$CLI_SCRIPT" "https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/${CLI_VERSION}/celarpass_cli.py" || echo_err "Fallo al descargar celarpass_cli.py."
    else
        echo_err "Necesitas tener instalado 'curl' o 'wget' para descargar los archivos."
    fi

    # Verificación de integridad del script descargado (SHA256 para la versión v1.0.4)
    EXPECTED_SHA="b99c50386d3520b8e080f5c973eeffc892a66e4dc09c64204f5514725c0ec93e"
    ACTUAL_SHA=$(sha256sum "$CLI_SCRIPT" | cut -d' ' -f1)
    if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
        rm -f "$CLI_SCRIPT"
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

    # Verificación de integridad del repositorio criptográfico base.
    # Comparamos el commit HEAD actual contra el hash esperado para asegurar
    # que el código clonado no fue alterado.
    EXPECTED_CORE_COMMIT="025db8e9f88251accfc9a09f64483c216fc1c080"
    ACTUAL_CORE_COMMIT=$(git -C "$CORE_REPO_PATH" rev-parse HEAD)
    if [ "$ACTUAL_CORE_COMMIT" != "$EXPECTED_CORE_COMMIT" ]; then
        rm -rf "$CORE_REPO_PATH"
        echo_err "Verificación de integridad fallida para celarpass_core. Commit esperado: $EXPECTED_CORE_COMMIT, obtenido: $ACTUAL_CORE_COMMIT. Posible compromiso del repositorio."
    fi
fi

# El repo de celarpass_core puede venir anidado (la raíz del repo clonado
# contiene OTRA carpeta celarpass_core/ adentro, que es el paquete real con
# generators.py, hibp.py, etc.) o plano (setup.py/pyproject.toml directamente
# en la raíz). Detectamos cuál es el caso e instalamos la carpeta correcta
# con pip, en vez de asumir una estructura fija. Esto cubre tanto Modo Local
# como Standalone con la misma lógica, evitando que se desincronicen entre sí.
PIP_INSTALL_TARGET=""
if [ -f "$CORE_REPO_PATH/setup.py" ] || [ -f "$CORE_REPO_PATH/pyproject.toml" ]; then
    PIP_INSTALL_TARGET="$CORE_REPO_PATH"
elif [ -f "$CORE_REPO_PATH/celarpass_core/setup.py" ] || [ -f "$CORE_REPO_PATH/celarpass_core/pyproject.toml" ]; then
    PIP_INSTALL_TARGET="$CORE_REPO_PATH/celarpass_core"
else
    if [ "$CURRENT_DIR" = "$INSTALL_DIR" ]; then
        echo_warn "No se encontró 'setup.py' ni 'pyproject.toml' en modo local. Se omitirá la instalación de celarpass_core con pip."
    else
        echo_err "No se encontró 'setup.py' ni 'pyproject.toml' en '$CORE_REPO_PATH' (ni en su posible subcarpeta anidada). No es posible instalar celarpass_core como paquete de Python. Verifica que el repositorio tenga metadata de empaquetado válida."
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

# NOTA: usamos un array (PIP_CMD=(...)) en vez de un string para PIP_CMD.
# Con un string, "$PIP_CMD install ..." sin comillas hace word-splitting
# y rompe si $VENV_DIR contiene espacios. Con un array y
# "${PIP_CMD[@]}" cada elemento se preserva intacto.
# IMPORTANTE: definimos PIP_CMD siempre, fuera del bloque de creación del venv,
# porque lo necesitamos también en reinstalaciones (ver más abajo).
PIP_CMD=("$VENV_DIR/bin/pip")

if [ "$VENV_IS_NEW" -eq 1 ]; then
    echo_info "Instalando dependencias requeridas..."
    "${PIP_CMD[@]}" install --quiet --upgrade pip
    # Instalamos las dependencias explícitas usando un archivo bloqueado con hashes
    # para evitar ataques de cadena de suministro en PyPI.
    if [ -f "$INSTALL_DIR/requirements-cli.txt" ]; then
        "${PIP_CMD[@]}" install --quiet --require-hashes -r "$INSTALL_DIR/requirements-cli.txt"
    elif [ -f "$INSTALL_DIR/requirements.txt" ]; then
        "${PIP_CMD[@]}" install --quiet -r "$INSTALL_DIR/requirements.txt"
    else
        echo_err "No se encontró requirements-cli.txt ni requirements.txt. Abortando instalación: no es posible verificar la integridad de las dependencias."
    fi
fi

# IMPORTANTE: esto corre SIEMPRE, tanto si el venv es nuevo como si ya existía.
# Si solo instalamos celarpass_core cuando el venv se crea por primera vez,
# un "git pull" en una reinstalación deja el código fuente actualizado en
# disco pero el paquete en site-packages queda con la versión vieja: el
# wrapper sigue ejecutando código desactualizado sin ningún error visible.
# PIP_INSTALL_TARGET ya resuelve el posible anidamiento del repo (ver arriba),
# por lo que esta misma lógica cubre tanto Modo Local como Standalone.
if [ -d "$PIP_INSTALL_TARGET" ]; then
    echo_info "Instalando/actualizando paquete celarpass_core en el entorno virtual..."
    "${PIP_CMD[@]}" install --quiet --force-reinstall --no-deps "$PIP_INSTALL_TARGET"
fi

# Crear el acceso global (wrapper)
# Verificamos que el directorio destino exista y sea escribible: en sistemas
# con filesystem inmutable o /usr/local/bin no estándar (algunos contenedores,
# NixOS, distros con /usr en solo-lectura) esto puede fallar silenciosamente.
BIN_DIR="$(dirname "$BIN_LINK")"
if [ ! -d "$BIN_DIR" ]; then
    mkdir -p "$BIN_DIR" || echo_err "No se pudo crear el directorio '$BIN_DIR'. Verifica permisos o si tu sistema usa una ruta distinta para binarios globales."
fi
if [ ! -w "$BIN_DIR" ]; then
    echo_err "'$BIN_DIR' no es escribible (posible filesystem de solo lectura). No se puede instalar el ejecutable global."
fi

echo_info "Creando ejecutable global en $BIN_LINK..."
cat > "$BIN_LINK" << EOF
#!/usr/bin/env bash
# Wrapper generado automáticamente para CelarPass CLI
# Ejecuta el script dentro de su propio entorno virtual aislado
set -euo pipefail
source "$VENV_DIR/bin/activate"
exec python3 "$CLI_SCRIPT" "\$@"
EOF

chmod +x "$BIN_LINK"

echo_info "✅ CelarPass CLI instalado exitosamente."
echo_info "Ahora puedes usar la herramienta globalmente en tu terminal:"
echo -e "  ${GREEN}celarpass-cli --help${NC}"
