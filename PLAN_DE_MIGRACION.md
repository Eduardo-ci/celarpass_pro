# Migración Completa de Marca: CipherPass a CelarPass

Este plan detalla los pasos requeridos para renombrar estructuralmente toda la aplicación, incluyendo el núcleo criptográfico, la CLI, la GUI, los scripts de empaquetado y la documentación. 

Se ejecutará en el nuevo directorio clonado: `/home/eduardo/DesckApp/celarpass_pro`.

## User Review Required

> [!NOTE]
> De acuerdo con tu sugerencia, el enfoque será **crear una nueva estructura limpia** para el núcleo. 
> 
> En lugar de lidiar con el historial del repositorio viejo, copiaremos el contenido de `cipherpass_core` a una nueva carpeta `celarpass_core`, haremos todos los cambios de marca (incluyendo clases internas y TOTP), y esta nueva carpeta estará lista para que la subas a GitHub como un repositorio completamente nuevo llamado `celarpass_core`.

---

## Proposed Changes

### FASE 1: Creación del nuevo Core (`celarpass_core`)
- Copiar el contenido de `cipherpass_core/` a una nueva carpeta `celarpass_core/`.
- Eliminar la carpeta `.git` dentro de `celarpass_core/` para desvincularlo del repositorio viejo (así podrás inicializarlo como uno nuevo luego).
- Eliminar la carpeta vieja `cipherpass_core/` de nuestro nuevo espacio de trabajo.

### FASE 2: Renombrado Estructural (Carpetas y Archivos)
- Renombrar `cipherpass_cli.py` a `celarpass_cli.py`.
- Renombrar `cipherpass.png` a `celarpass.png`.
- Renombrar `resources/icons/cipherpass.ico` a `celarpass.ico`.
- Renombrar `resources/icons/cipherpass.png` a `celarpass.png`.
- Renombrar `tests/test_cipherpass_core.py` a `tests/test_celarpass_core.py`.

---

### FASE 3: Actualización de Importaciones y Código Fuente
Corregiremos todas las importaciones e identificadores internos (clases, URIs) en todo el código.

#### [MODIFY] Archivos Python (GUI, CLI, Core y Tests)
- `main.py`, `celarpass_cli.py`, `tests/test_celarpass_core.py`:
  - Cambiar `from cipherpass_core import...` a `from celarpass_core import...`.
- `celarpass_core/generators.py`:
  - Cambiar el emisor en la URI de TOTP de `CipherPass` a `CelarPass`.
- Código general:
  - Renombrar clases internas si existen referencias directas como `CipherPassEngine` a `CelarPassEngine`.

---

### FASE 4: Scripts de Construcción y Despliegue
Alinearemos los scripts bash y de InnoSetup para que empaqueten usando los nuevos nombres y apunten al nuevo repositorio.

#### [MODIFY] Scripts de Compilación
- `build_package.sh`, `build_appimage.sh`:
  - Cambiar las referencias para clonar el repositorio: de `cipherpass_core.git` a `celarpass_core.git`.
  - Cambiar los `--include-package=cipherpass_core` en Nuitka a `celarpass_core`.
  - Actualizar los nombres de los íconos (ej. `cipherpass.png` -> `celarpass.png`).
- `installer.iss`:
  - Actualizar `SetupIconFile=resources\icons\celarpass.ico`.
- `install_cli.sh`:
  - Actualizar referencias de `cipherpass_cli.py` a `celarpass_cli.py`.
- `.github/workflows/build-windows.yml` y `codeql-analysis.yml`:
  - Actualizar paths y paquetes a incluir.

---

### FASE 5: Documentación y Metadatos
Reemplazaremos todas las menciones legibles para el usuario de "CipherPass" a "CelarPass".

#### [MODIFY] Archivos de Texto
- `README.md`, `CONTRIBUTING.md`, `CLI_INSTRUCTIONS.md`, `SECURITY.md`, `dependencias.sh`, `update_translations.sh`:
  - Búsqueda y reemplazo global de `CipherPass` por `CelarPass`.
  - Búsqueda y reemplazo global de `cipherpass` por `celarpass`.
- Carpeta `docs/` y `mkdocs.yml`:
  - Reemplazo global en los archivos markdown para que el sitio de MkDocs refleje la nueva marca.

---

## Verification Plan

### Automated Tests
- Ejecutar `pytest tests/` para asegurar que las importaciones y la lógica sigan funcionando con el nuevo nombre `celarpass_core`.

### Manual Verification
- Ejecutar `python3 celarpass_cli.py -h` para verificar que el manual de ayuda diga correctamente `usage: celarpass_cli.py`.
- Ejecutar `main.py` para asegurar que la interfaz gráfica inicie sin errores de importación.
