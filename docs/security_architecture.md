# Arquitectura de Seguridad 🛡️

CelarPass PRO fue diseñado desde cero con un enfoque de seguridad proactiva y **offline-first**. En esta sección detallamos las decisiones arquitectónicas y los algoritmos criptográficos que garantizan la privacidad de tus datos.

## 1. Enfoque Offline-First
La principal premisa de CelarPass es que **tus datos nunca abandonan tu dispositivo**. A diferencia de los gestores de contraseñas basados en la nube, CelarPass no sincroniza tus bóvedas ni tus contraseñas maestras con ningún servidor externo. Todo el cifrado y descifrado ocurre localmente en la memoria de tu computadora.

## 2. Criptografía en Reposo (La Bóveda)
Cuando decides exportar información sensible utilizando la función de Bóveda (Vault), CelarPass aplica los más altos estándares de cifrado simétrico:

*   **Algoritmo de Cifrado:** Se utiliza **AES-GCM** (Advanced Encryption Standard con Galois/Counter Mode). Este es un esquema de cifrado autenticado (AEAD) que no solo garantiza la confidencialidad de los datos, sino también su integridad, asegurando que el archivo no haya sido modificado maliciosamente.
*   **Derivación de Claves (KDF):** Para convertir tu contraseña maestra humana en una clave criptográfica de 256 bits, utilizamos **Argon2id**. Este es el algoritmo ganador del *Password Hashing Competition*.
    *   *Resistencia a Fuerza Bruta:* Argon2id está configurado con parámetros agresivos (consumo de ~256MB de RAM) para hacer extremadamente costosos y lentos los ataques offline mediante tarjetas gráficas (GPUs) o hardware especializado (ASICs).
    *   *Fallback:* Si el sistema operativo no soporta Argon2, la aplicación cuenta con un respaldo seguro utilizando `PBKDF2-HMAC-SHA256` con 1,000,000 de iteraciones.

## 3. Verificación de Brechas (HIBP) y K-Anonymity
La validación de contraseñas expuestas utiliza la API de *Have I Been Pwned* (HIBP), pero lo hace implementando el modelo de **K-Anonymity** para preservar tu privacidad de forma absoluta:
1.  Tu contraseña se hashea localmente utilizando SHA-1.
2.  Solo los **primeros 5 caracteres** de ese hash se envían por la red.
3.  El servidor de HIBP devuelve una lista de todos los hashes filtrados que comienzan con esos 5 caracteres.
4.  La comparación final se realiza localmente en tu dispositivo.

De esta forma, **es matemáticamente imposible** que el servidor, tu proveedor de internet, o un atacante interceptando la red puedan conocer qué contraseña estás validando.

## 4. Generación de Entropía
Para la creación de contraseñas, frases (Diceware) y tokens, nunca utilizamos generadores de números pseudoaleatorios predecibles (como el módulo `random` estándar). Todo el material criptográfico se genera a través de `secrets.SystemRandom()`, el cual interactúa directamente con el **CSPRNG** (Generador de Números Pseudoaleatorios Criptográficamente Seguro) de tu sistema operativo (e.g., `/dev/urandom` en Linux/macOS, o `CryptGenRandom` en Windows).

## 5. Saneamiento de Memoria (Scrubbing)
En lenguajes de alto nivel como Python, la gestión de memoria (Garbage Collection) puede dejar restos de variables en la memoria RAM mucho después de haber sido usadas. Para mitigar ataques de volcado de memoria (Memory Dumps) o ataques de arranque en frío (Cold Boot Attacks):
*   Las referencias a contraseñas maestras, semillas TOTP y claves AES derivadas son eliminadas explícitamente usando la instrucción `del` inmediatamente después de cumplir su función.

## 6. Manejo de Secretos Multi-Hilo
Operaciones intensivas, como la consulta de bases de datos de contraseñas expuestas, se realizan de forma asíncrona mediante un `QThreadPool`. Esto previene que la interfaz gráfica se congele, y permite que las credenciales evaluadas existan en la memoria temporal de un hilo volátil que se destruye automáticamente al finalizar, limitando aún más la ventana de exposición.