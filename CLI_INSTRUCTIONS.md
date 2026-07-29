# CelarPass CLI - User Manual / Manual de Uso

*(Scroll down for the Spanish version / Desplázate hacia abajo para la versión en español)*

---

# 🇬🇧 English Version

`celarpass-cli` is a cryptographic tool designed for SysAdmins, offering features such as password generation, validation against exposed password databases (Have I Been Pwned), and secure data encryption/decryption (vaults).

## Basic Usage
```bash
celarpass-cli [command] [arguments...]
```

### Global Arguments
*   `--json`: Outputs the result as a raw, machine-readable JSON object instead of formatted text. Ideal for bash scripts and CI/CD pipelines.

---

## Available Commands

### 1. `generate`
Generates a secure, cryptographically strong password.

**Optional arguments:**
*   `-l`, `--length <integer>`: Defines the length of the generated password (default: `16`).
*   `--no-upper`: Excludes uppercase letters.
*   `--no-nums`: Excludes numbers.
*   `--no-syms`: Excludes symbols or special characters.
*   `--avoid-ambiguous`: Avoids ambiguous characters that can be visually confused (like `I`, `l`, `1`, `O`, `0`).
*   `-c`, `--copy`: Copies the generated password directly to the system clipboard instead of printing it to standard output.
*   `--analyze`: Evaluates the password's entropy and strength using `zxcvbn`, displaying a formatted table with the score and estimated crack time.

**Examples:**
```bash
# Generate a standard 16-character password
celarpass-cli generate

# Generate and analyze a 24-character password, then copy it to clipboard
celarpass-cli generate -l 24 --analyze -c
```

---

### 2. `totp`
Generates a new random Base32 secret, ready to be used in two-factor authentication (TOTP) apps like Google Authenticator or Authy.

**Optional arguments:**
*   `-c`, `--copy`: Copies the generated secret to the system clipboard.

**Example:**
```bash
celarpass-cli totp -c
```

---

### 3. `hibp`
Checks if a password has been exposed in data breaches using the *Have I Been Pwned* (HIBP) API.

**🛡️ Built-in Security:** To prevent password leakage, the password is **never** passed as a command-line argument. The tool will securely prompt you for it (hidden input). 
*Automation:* If you pipe data into this command, it will silently read from standard input (`stdin`) instead of prompting interactively.

**Example:**
```bash
# Interactive mode
celarpass-cli hibp

# Automation / Pipeline mode
echo "mypassword123" | celarpass-cli hibp --json
```

---

### 4. `vault-export`
Encrypts text or confidential information using AES-GCM to be stored in a secure vault, producing a JSON string with the encrypted data.

**🛡️ Built-in Security:** The master password is always requested interactively.

**Arguments:**
*   `data` *(required)*: The text you want to encrypt. Provide the text directly or use `-` to read from standard input (*stdin*).
*   `--argon2` *(optional)*: Forces the use of the Argon2id algorithm to derive the cryptographic key, providing better security against brute-force attacks.

**Examples:**
```bash
celarpass-cli vault-export "My top secret info" --argon2
echo "Secret text" | celarpass-cli vault-export -
```

---

### 5. `vault-import`
Takes the JSON data from a previously exported vault and decrypts it, returning the original plain text.

**🛡️ Built-in Security:** The master password is always requested interactively.

**Arguments:**
*   `data` *(required)*: The JSON containing the encrypted data. Use `-` to read from standard input.

**Example:**
```bash
cat vault.json | celarpass-cli vault-import -
```

---

### 6. `token`
Generates a secure token to be used in APIs, cloud services, or universal unique identifiers (UUID v4).

**Optional arguments:**
*   `-m`, `--mode <0|1|2|3>`: Specifies the format of the generated token. (Default: `0`).
    *   `0`: URL-safe (Base64url without padding).
    *   `1`: Hexadecimal.
    *   `2`: UUID v4.
    *   `3`: Bearer Token (URL-safe prefixed with `Bearer `).
*   `-l`, `--length <integer>`: Defines the length of the token in bytes for modes 0, 1, and 3 (Default: `32`).
*   `-c`, `--copy`: Copies the generated token to the system clipboard.

**Examples:**
```bash
celarpass-cli token --mode 2
celarpass-cli token -m 3 -l 64 -c
```

<br><br><br>

---

# 🇪🇸 Versión en Español

`celarpass-cli` es una herramienta criptográfica diseñada para SysAdmins que ofrece funcionalidades como la generación de contraseñas, validación en bases de datos de contraseñas expuestas y cifrado/descifrado seguro de datos (bóvedas).

## Uso Básico
```bash
celarpass-cli [comando] [argumentos...]
```

### Argumentos Globales
*   `--json`: Muestra el resultado como un objeto JSON puro en lugar de texto formateado. Ideal para integrarlo en scripts de bash y pipelines CI/CD.

---

## Comandos Disponibles

### 1. `generate`
Genera una contraseña segura y criptográficamente fuerte.

**Argumentos opcionales:**
*   `-l`, `--length <entero>`: Define la longitud de la contraseña generada (por defecto es `16`).
*   `--no-upper`: Excluye las letras mayúsculas.
*   `--no-nums`: Excluye los números.
*   `--no-syms`: Excluye los símbolos o caracteres especiales.
*   `--avoid-ambiguous`: Evita incluir caracteres ambiguos que pueden ser fáciles de confundir visualmente (`I`, `l`, `1`, `O`, `0`).
*   `-c`, `--copy`: Copia la contraseña generada directamente al portapapeles del sistema en lugar de imprimirla en pantalla.
*   `--analyze`: Evalúa la entropía y fortaleza de la contraseña usando `zxcvbn`, mostrando una tabla con la puntuación y el tiempo estimado de crackeo.

**Ejemplos de uso:**
```bash
# Generar una contraseña estándar de 16 caracteres
celarpass-cli generate

# Generar y analizar una contraseña de 24 caracteres, y copiar al portapapeles
celarpass-cli generate -l 24 --analyze -c
```

---

### 2. `totp`
Genera un nuevo secreto aleatorio en Base32, listo para ser utilizado en aplicaciones de autenticación de dos factores (TOTP) como Google Authenticator o Authy.

**Argumentos opcionales:**
*   `-c`, `--copy`: Copia el secreto generado al portapapeles.

**Ejemplo de uso:**
```bash
celarpass-cli totp -c
```

---

### 3. `hibp`
Comprueba si una contraseña ha sido expuesta en filtraciones de datos, haciendo uso de la API de *Have I Been Pwned* (HIBP).

**🛡️ Seguridad Integrada:** Para prevenir la filtración de tu contraseña, esta **nunca** se pasa como argumento de la línea de comandos. La herramienta te la solicitará de forma segura (oculta) durante la ejecución. 
*Automatización:* Si pasas datos a través de tuberías (pipes), el comando leerá silenciosamente desde la entrada estándar (`stdin`) sin bloquearse con prompts interactivos.

**Ejemplo de uso:**
```bash
# Modo interactivo
celarpass-cli hibp

# Modo automatizado / Pipes
echo "miclavesecreta" | celarpass-cli hibp --json
```

---

### 4. `vault-export`
Cifra un texto o información confidencial utilizando AES-GCM para ser almacenado en una bóveda segura, produciendo un archivo JSON con los datos cifrados.

**🛡️ Seguridad Integrada:** La contraseña maestra de la bóveda siempre se solicita de manera interactiva.

**Argumentos:**
*   `data` *(requerido)*: El texto que deseas cifrar. Puedes proporcionar el texto directamente, o usar el guion `-` para que la herramienta lea la información desde la entrada estándar (*stdin*).
*   `--argon2` *(opcional)*: Fuerza el uso del algoritmo Argon2id para derivar la clave criptográfica en lugar del algoritmo predeterminado.

**Ejemplos de uso:**
```bash
celarpass-cli vault-export "Mi información ultrasecreta" --argon2
echo "Texto secreto" | celarpass-cli vault-export -
```

---

### 5. `vault-import`
Recibe los datos en formato JSON de una bóveda previamente exportada y los descifra, devolviendo el texto original en plano.

**🛡️ Seguridad Integrada:** La contraseña maestra de la bóveda siempre se solicita de manera interactiva.

**Argumentos:**
*   `data` *(requerido)*: El JSON que contiene los datos cifrados. También acepta `-` para leer desde la entrada estándar.

**Ejemplo de uso:**
```bash
cat boveda.json | celarpass-cli vault-import -
```

---

### 6. `token`
Genera un token seguro para ser utilizado en APIs, servicios en la nube, o identificadores únicos universales (UUID v4).

**Argumentos opcionales:**
*   `-m`, `--mode <0|1|2|3>`: Especifica el formato del token generado. (Por defecto: `0`).
    *   `0`: URL-safe (Base64url sin relleno).
    *   `1`: Hexadecimal.
    *   `2`: UUID v4.
    *   `3`: Bearer Token. Mismo que el modo `0` pero con el prefijo `Bearer `.
*   `-l`, `--length <entero>`: Define la longitud del token en bytes para los modos 0, 1 y 3 (Por defecto: `32`).
*   `-c`, `--copy`: Copia el token generado al portapapeles.

**Ejemplos de uso:**
```bash
celarpass-cli token --mode 2
celarpass-cli token -m 3 -l 64 -c
```
