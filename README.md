# CelarPass 🔐

**CelarPass** is a powerful, secure, and open-source desktop application designed to generate, validate, and protect cryptographic credentials. Built with **Python** and **Qt (PySide6)**, it strictly adheres to an *offline-first* privacy model.

---

**CelarPass** es una aplicación de escritorio potente, segura y de código abierto diseñada para generar, validar y proteger credenciales criptográficas. Desarrollada con **Python** y **Qt (PySide6)**, sigue estrictamente un modelo de privacidad *offline-first*.

---

## ✨ Features / Características

* **Advanced Credential Generation:** Create highly secure passwords, Diceware passphrases, custom usernames, and API/Cloud tokens.
  
  **Generación avanzada de credenciales:** Crea contraseñas altamente seguras, frases de contraseña Diceware, nombres de usuario personalizados y tokens de API/Cloud.

* **Compliance Presets:** Enforce security policies effortlessly with built-in presets for Active Directory, AWS IAM, PCI-DSS, and NIST 800-63B.
  
  **Preajustes de cumplimiento normativo:** Aplica políticas de seguridad sin esfuerzo con preajustes integrados para Active Directory, AWS IAM, PCI-DSS y NIST 800-63B.

* **Proactive Security Validation / Validación de seguridad proactiva:**
  * Analyzes password strength and estimates crack times using `zxcvbn`, dynamically augmented with mathematical entropy to prevent false negatives on highly random passwords.
    
    Analiza la fortaleza de contraseñas y estima tiempos de descifrado mediante `zxcvbn`, incrementado dinámicamente con entropía matemática para prevenir falsos negativos en contraseñas altamente aleatorias.
  * Checks passwords against known data breaches via the **Have I Been Pwned (HIBP)** API using *k-anonymity* (only the first 5 characters of the SHA-1 hash are sent).
    
    Comprueba contraseñas contra filtraciones de datos conocidas a través de la API de **Have I Been Pwned (HIBP)** usando *k-anonimato* (solo se envían los primeros 5 caracteres del hash SHA-1).

* **Encrypted Vault / Bóveda cifrada:** Securely import and export your credentials. Uses **Argon2id** for key derivation and **Fernet (AES-128 in CBC mode with HMAC)** for authenticated encryption.
  
  Importa y exporta tus credenciales de forma segura. Utiliza **Argon2id** para la derivación de claves y **Fernet (AES-128 en modo CBC con HMAC)** para cifrado autenticado.

* **TOTP/MFA Generator / Generador TOTP/MFA:** Generate Time-based One-Time Passwords (TOTP) and export them as QR codes for easy mobile scanning.
  
  Genera contraseñas de un solo uso basadas en tiempo (TOTP) y expórtalas como códigos QR para escanearlos fácilmente desde el móvil.

* **Multi-language Support / Soporte multilingüe:** Available in English, Spanish, and Portuguese.
  
  Disponible en inglés, español y portugués.
  *(See how to add a new language in the section below / Mira cómo agregar un nuevo idioma en la sección de abajo).*

---

## 🚀 Installation & Usage / Instalación y uso

### Prerequisites / Requisitos previos

Ensure you have Python 3 installed. The application requires the following main libraries:

Asegúrate de tener Python 3 instalado. La aplicación requiere las siguientes bibliotecas principales:

* `PySide6`
* `cryptography`
* `zxcvbn`
* `platformdirs`
* `requests`
* `argon2-cffi` (for secure vault encryption / para cifrado seguro de la bóveda)
* `qrcode` & `pillow` (for TOTP QR generation / para la generación de QR TOTP)

### Running from Source / Ejecutar desde el código fuente

1. Clone the repository and its core submodule / Clona el repositorio y su submódulo principal:
   ```bash
   git clone git@github.com:YOUR_USERNAME/CelarPass_Pro.git
   cd CelarPass_Pro
   git clone git@github.com:YOUR_USERNAME/celarpass-core.git celarpass_core
   ```

2. Create a virtual environment and install dependencies / Crea un entorno virtual e instala las dependencias:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt # Or install the packages manually / O instala los paquetes manualmente
   ```

3. Run the application / Ejecuta la aplicación:
   ```bash
   python main.py
   ```

---

## 📦 Packaging (Debian/Ubuntu) / Empaquetado (Debian/Ubuntu)

CelarPass includes a complete bash script (`build_package.sh`) to compile the application into native C code using **Nuitka** and package it as a standalone `.deb` installer.

CelarPass incluye un script bash completo (`build_package.sh`) para compilar la aplicación en código C nativo usando **Nuitka** y empaquetarla como un instalador `.deb` independiente.

To build the Debian package / Para construir el paquete Debian:
```bash
chmod +x build_package.sh
./build_package.sh
```
*Note: Make sure you have `dpkg-deb`, `gcc`, and `patchelf` installed on your system before running the build script.*

*Nota: Asegúrate de tener instalados `dpkg-deb`, `gcc` y `patchelf` en tu sistema antes de ejecutar el script de compilación.*

---
## 💻 Command Line Interface (CLI) / Interfaz de Línea de Comandos (CLI)

CelarPass includes a terminal tool (`celarpass_cli.py`) ideal for **SysAdmins, DevOps, and pipeline automation (CI/CD)**. It allows you to generate credentials, validate security, and encrypt secrets directly from the console, and can be linked to other tools via standard input (`stdin`).

CelarPass incluye una herramienta de terminal (`celarpass_cli.py`) ideal para **SysAdmins, DevOps y automatización de pipelines (CI/CD)**. Permite generar credenciales, validar seguridad y cifrar secretos directamente desde la consola, pudiendo enlazarse con otras herramientas mediante la entrada estándar (`stdin`).

### Standalone CLI Installation / Instalación independiente de la CLI
If you only need the CLI (e.g., on a server), you can install it globally with a single command without cloning the entire repository:

Si solo necesitas la CLI (ej. en un servidor), puedes instalarla globalmente con un solo comando sin necesidad de clonar el repositorio completo:

```bash
curl -sL https://raw.githubusercontent.com/Eduardo-ci/celarpass_pro/main/install_cli.sh | sudo bash
```
Once installed, you can use the `celarpass-cli` command globally.

Una vez instalada, puedes usar el comando `celarpass-cli` de forma global.

**Examples of use/ Ejemplos de uso:**
```bash
# Generate a 24-character password, avoiding ambiguities
# Generar una contraseña de 24 caracteres evitando ambiguos
celarpass-cli generate --length 24 --avoid-ambiguous

# Generate a secret TOTP and its URI
# Generar un secreto TOTP y su URI
celarpass-cli totp -a user@correo.com -i "Mi Empresa"

# Check if a password has been compromised (will prompt for hidden input)
# Comprobar si una contraseña está comprometida (pedirá la contraseña de forma oculta)
celarpass-cli hibp

# Encrypt the contents of a file directly to the vault
# Cifrar el contenido de un archivo directamente hacia la bóveda
cat secreto.txt | celarpass-cli vault-export - --argon2

# Decrypt content
# Descifrar contenido
cat boveda.cpv | celarpass-cli vault-import -
```

---
## 📚 Documentation / Documentación

CelarPass uses **MkDocs** for its documentation and auto-generated API references.

CelarPass utiliza **MkDocs** para su documentación y referencias de API generadas automáticamente.

To build and view the documentation locally / Para construir y ver la documentación localmente:

```bash
mkdocs serve
```
Then, open `http://127.0.0.1:8000` in your web browser.

Luego, abre `http://127.0.0.1:8000` en tu navegador web.

---

## 🌍 Contributing a New Language / Contribuir con un nuevo idioma

Thanks to our dynamic i18n system, adding a new language (e.g., French `fr`) is extremely simple:

Gracias a nuestro sistema i18n dinámico, agregar un nuevo idioma (ej. Francés `fr`) es extremadamente simple:

1. Add your language code to `update_translations.sh`. / Agrega el código de tu idioma a `update_translations.sh`.
2. Run `./update_translations.sh` to generate the `.ts` source file. / Ejecuta el script para generar el archivo fuente `.ts`.
3. Open `resources/lang/lang_fr.ts` with **Qt Linguist** and translate the strings. / Abre el archivo con **Qt Linguist** y traduce los textos.
4. Run `./update_translations.sh` again to compile the `.qm` binary. / Ejecuta el script nuevamente para compilar el binario `.qm`.
5. Restart CelarPass. Your language will automatically appear in the top Menu Bar! / ¡Reinicia CelarPass y tu idioma aparecerá automáticamente en el menú superior!

---

## 🛡️ License / Licencia

This project is licensed under the **GNU AGPLv3 License**. See the `LICENSE` file for details.

Este proyecto está licenciado bajo la **Licencia GNU AGPLv3**. Consulta el archivo `LICENSE` para más detalles.

CelarPass guarantees that your master passwords and generated keys never leave your device unencrypted. The only network request made is an optional, anonymous prefix-hash check to HIBP.

CelarPass garantiza que tus contraseñas maestras y claves generadas nunca abandonen tu dispositivo sin cifrar. La única solicitud de red que se realiza es una verificación anónima y opcional de prefijo de hash a HIBP.

---
Lo que fue para amigos y colegas hoy lo comparto con la comunidad, tal ves a alguien le puede ser útil, con eso estoy mas que satisfecho.

What was once for friends and colleagues I now share with the community; perhaps it can be useful to someone, and with that I am more than satisfied.

