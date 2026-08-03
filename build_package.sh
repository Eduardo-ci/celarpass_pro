#!/usr/bin/env bash
# set -u  → falla si se usa una variable no definida
# set -o pipefail → falla si cualquier comando de un pipeline falla
set -euo pipefail

# 📦 Configuración del paquete
APP_NAME="celarpass"
VERSION="1.0.4"
ARCH="amd64"
DEB_FILE="${APP_NAME}_${VERSION}_${ARCH}.deb"
BUILD_DIR="build"
DIST_DIR="dist"
DEB_DIR="${APP_NAME}-deb"
VENV_DIR=".venv"

# 🎨 Colores para terminal
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ✅ Validaciones iniciales
check_prerequisites() {
    command -v python3 >/dev/null 2>&1 || echo_err "python3 no encontrado"
    command -v python3-config >/dev/null 2>&1 || echo_err "Cabeceras de Python no encontradas, requeridas por Nuitka (instala: sudo apt install python3-dev)"
    command -v dpkg-deb >/dev/null 2>&1 || echo_err "dpkg-deb no encontrado (instala: sudo apt install dpkg)"
    command -v gcc >/dev/null 2>&1 || echo_err "Compilador C (gcc) no encontrado (instala: sudo apt install build-essential)"
    command -v patchelf >/dev/null 2>&1 || echo_err "patchelf no encontrado, requerido por Nuitka (instala: sudo apt install patchelf)"
    
    [ -f "main.py" ] || echo_err "No se encontró main.py. Ejecuta el script desde la raíz del proyecto"
    [ -d "resources" ] || echo_err "Carpeta 'resources' no encontrada"
    [ -d "ui" ] || echo_err "Carpeta 'ui' no encontrada"
}

# 🛠 Paso 1: Entorno virtual e instalación de dependencias
setup_venv() {
    echo_info "📦 Creando entorno virtual limpio..."
    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    echo_info "📥 Instalando dependencias desde requirements.txt (con hashes verificados si disponibles)..."
    pip install --quiet --upgrade pip setuptools wheel
    if [ -f "requirements.txt" ]; then
        pip install --quiet -r requirements.txt
        # Instalar Nuitka explícitamente ya que es una dependencia de construcción y no suele estar en requirements.txt
        pip install --quiet nuitka
    else
        echo_warn "requirements.txt no encontrado. Instalando sin versiones fijadas (menos seguro)."
        pip install --quiet PySide6 zxcvbn cryptography platformdirs nuitka qrcode pillow requests argon2-cffi
    fi
}

# 📥 Paso 1.5: Sincronizar el Core Criptográfico (Submódulo)
fetch_core() {
    # SEGURIDAD (A-02): GH_USER debe estar definido como variable de entorno o
    # en un archivo .env antes de ejecutar este script. La sintaxis :? termina
    # el script con error si la variable está vacía o sin definir.
    # Ejemplo de uso: GH_USER=mi_usuario_github ./build_package.sh
    local gh_user="${GH_USER:?'ERROR: La variable GH_USER debe estar definida. Ej: GH_USER=mi_usuario ./build_package.sh'}"
    
    echo_info "🌐 Obteniendo el núcleo criptográfico (celarpass_core)..."
    if [ -d "celarpass_core/.git" ]; then
        echo_info "Actualizando el repositorio público local..."
        git -C celarpass_core fetch origin
    elif [ -d "celarpass_core" ]; then
        echo_warn "La carpeta 'celarpass_core' ya existe pero no es un repositorio Git. Se usará la versión local sin actualizar."
    else
        echo_info "Clonando repositorio público celarpass_core..."
        # Se usa SSH para clonar sin pedir contraseña (requiere llaves SSH configuradas)
        git clone "git@github.com:${gh_user}/celarpass_core.git" celarpass_core
    fi
    # SEGURIDAD (A-02): Verificación estricta contra un commit conocido
    # Hash actual del repositorio público obtenido hoy:
    local EXPECTED_COMMIT="025db8e9f88251accfc9a09f64483c216fc1c080"
    
    # Solo verificamos si realmente es un repositorio clonado (evita errores con tu código local)
    if [ -d "celarpass_core/.git" ]; then
        git -C celarpass_core checkout -q "$EXPECTED_COMMIT"
        local actual_commit
        actual_commit=$(git -C celarpass_core rev-parse HEAD)
        if [ "${actual_commit}" != "${EXPECTED_COMMIT}" ]; then
            echo_err "Hash de celarpass_core (${actual_commit:0:7}) no coincide con el esperado (${EXPECTED_COMMIT:0:7}). ¡Posible manipulación de código!"
        fi
        echo_info "✅ Integridad verificada correctamente (Commit seguro: ${actual_commit:0:7})"
    else
        echo_warn "Se omitió la verificación de seguridad A-02 porque estás usando la carpeta local (sin .git)."
    fi
}

# ⚙️ Paso 2: Compilación con Nuitka (Código C Nativo)
build_executable() {
    echo_info "🔨 Traduciendo a C y compilando ejecutable nativo (esto tomará varios minutos)..."
    
    python3 -m nuitka \
        --standalone \
        --onefile \
        --enable-plugin=pyside6 \
        --include-data-dir="resources=resources" \
        --include-data-dir="ui=ui" \
        --include-package=celarpass_core \
        --output-dir="$DIST_DIR" \
        --output-filename="$APP_NAME" \
        --remove-output \
        --disable-console \
        main.py
    
    [ -f "$DIST_DIR/$APP_NAME" ] || echo_err "Fallo en la compilación. Revisa la salida de Nuitka"
}

# 📁 Paso 3: Estructura del paquete Debian
prepare_deb_structure() {
    echo_info "🗂 Preparando estructura .deb..."
    rm -rf "$DEB_DIR"
    mkdir -p "$DEB_DIR"/{DEBIAN,usr/{bin,share/applications,share/pixmaps},opt/"$APP_NAME"}

    # Copiar binario y permisos
    cp "$DIST_DIR/$APP_NAME" "$DEB_DIR/opt/$APP_NAME/"
    chmod 755 "$DEB_DIR/opt/$APP_NAME/$APP_NAME"
    
    # Copiar icono para el sistema
    if [ -f "celarpass.png" ]; then
        cp "celarpass.png" "$DEB_DIR/usr/share/pixmaps/${APP_NAME}.png"
    fi

    # Enlace global en /usr/bin
    ln -s "/opt/$APP_NAME/$APP_NAME" "$DEB_DIR/usr/bin/$APP_NAME"

    # Archivo .desktop
    cat > "$DEB_DIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=CelarPass
Exec=/usr/bin/$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=Utility;Security;
Comment=Generador y validador de contraseñas criptográficas
EOF

    # Metadatos DEBIAN/control
    cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: libc6, libgl1, libx11-6, libxcb1, libxkbcommon0, libdbus-1-3, fontconfig, libqt6core6, libqt6gui6, libqt6widgets6
Maintainer: Eduardo Mallo <eduardo.mallo@email.com>
Description: Generador seguro de contraseñas y frases Diceware
 Aplicación de escritorio para generar, validar y gestionar credenciales
 con cifrado Fernet y análisis de entropía/zxcvbn.
EOF
}

# 🏗 Paso 4: Construcción del .deb
build_deb() {
    echo_info "📦 Empaquetando .deb..."
    dpkg-deb --build --root-owner-group "$DEB_DIR" "$DEB_FILE"
    echo_info "✅ Generado: $(realpath "$DEB_FILE")"
}

# 🧹 Paso 5: Limpieza opcional
cleanup() {
    echo_info "🧹 Limpiando temporales..."
    rm -rf "$BUILD_DIR" "$DEB_DIR"
    deactivate 2>/dev/null || true
    echo_info "✨ Proceso finalizado"
}

# 🚀 Ejecución principal
main() {
    check_prerequisites
    setup_venv
    fetch_core
    build_executable
    prepare_deb_structure
    build_deb
    cleanup
    
    echo_info "📌 Para instalar: sudo dpkg -i $DEB_FILE"
    echo_info "📌 Para ejecutar: $APP_NAME"
}

main "$@"