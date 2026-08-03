FEATURES POR TIER:
Free: generador de contraseñas, frases Diceware, usernames, analizador de fortaleza básico
PRO: tokens API/cloud, compliance presets, verificación HIBP, bóveda cifrada exportable, generador TOTP/MFA

────────────────────────────────────────────────────────────

FASE 1 — MVP DEVOPS (sin dependencias nuevas):

1.1 Generador de tokens API/Cloud:
  - Añadir generate_api_token() y generate_uuid4() a PasswordEngine
  - Usar secrets.token_urlsafe() y uuid.uuid4(); NO pasar por StrengthAnalyzer
  - Nueva pestaña en .ui: "Tokens API & Nube"

1.2 Compliance Presets:
  - Estructura de datos estática con reglas para: Active Directory, AWS IAM, PCI-DSS, NIST 800-63B
  - QComboBox en la UI principal para seleccionar política
  - Al seleccionar: sobreescribir spinBoxes/checkBoxes + mostrar badge "Modo Compliance activo"
  - Botón explícito para volver al modo manual (no deshabilitar sin escape)

FASE 2 — SEGURIDAD PROACTIVA (dependencia nueva: requests o httpx):

2.1 HIBP en StrengthAnalyzer:
  - Hash SHA-1 local con hashlib; enviar solo los primeros 5 chars del hash (k-anonymity)
  - Endpoint: api.pwnedpasswords.com/range/{prefix}; timeout=3s; manejo offline
  - Comparar sufijo localmente; nunca enviar la contraseña completa a ningún servicio

2.2 Concurrencia en UI:
  - Delegar la llamada HTTP a QRunnable + QThreadPool
  - Emitir Signal al hilo principal para actualizar ProgressBar y labels
  - Control opt-in: QCheckBox "Verificar en HIBP" (deshabilitado por defecto)

FASE 3 — CRIPTOGRAFÍA AVANZADA (dependencias: argon2-cffi, qrcode):

3.1 Bóveda cifrada exportable:
  - NO reutilizar CryptoManager; lógica nueva en VaultExporter
  - KDF: Argon2id (argon2-cffi) con parámetros explícitos (memory_cost, time_cost, parallelism)
    Fallback: hashlib.pbkdf2_hmac con salt de 16 bytes si argon2-cffi no está disponible
  - Cifrado AEAD: Fernet o AES-GCM sobre la clave derivada
  - Formato del archivo de salida: empaquetar {salt, kdf_params, ciphertext} en JSON o binario estructurado
  - Saneamiento: del explícito de referencias a contraseña maestra y clave derivada post-guardado
  - Captura de contraseña maestra: QInputDialog con EchoMode.Password

3.2 Generador TOTP:
  - Generar 20 bytes con secrets.token_bytes(); codificar en Base32 sin padding (base64.b32encode)
  - Mostrar semilla Base32 textualmente en QLineEdit de solo lectura
  - Si qrcode disponible: armar URI otpauth://totp/CelarPass:{label}?secret={seed}&issuer=CelarPass
    Renderizar QR como QPixmap en QLabel; botón para guardar imagen PNG