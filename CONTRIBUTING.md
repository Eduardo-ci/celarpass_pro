# Contribuyendo a CelarPass 🤝

¡Gracias por tu interés en contribuir a **CelarPass**! Al ser un proyecto de código abierto bajo la licencia GNU AGPLv3, la colaboración de la comunidad es esencial para mantener y mejorar la seguridad, funcionalidad y accesibilidad de la aplicación.

Este documento te guiará sobre cómo puedes colaborar en el proyecto.

## 🛠️ ¿Cómo puedes ayudar?

Hay muchas formas de contribuir, no todo requiere escribir código:

1. **Reportar Errores (Bugs):** Si encuentras un fallo, abre un *Issue* describiendo el problema, cómo reproducirlo y tu entorno (SO, versión de Python).
2. **Sugerir Mejoras:** ¿Tienes una idea genial? Abre un *Issue* con la etiqueta `enhancement` explicando tu propuesta y cómo beneficiaría a los usuarios.
3. **Traducciones (I18n):** CelarPass soporta múltiples idiomas. Puedes ayudar a mejorar las traducciones existentes o agregar nuevos idiomas (ver sección de traducciones).
4. **Escribir Código:** Puedes resolver *Issues* abiertos, mejorar la eficiencia del motor criptográfico (`celarpass_core`), o añadir nuevas funcionalidades a la interfaz.
5. **Mejorar Documentación:** Ayuda a hacer los manuales, *READMEs* o comentarios en el código más claros y accesibles.

## 💻 Entorno de Desarrollo

Para empezar a programar en CelarPass, sigue estos pasos:

1. **Haz un Fork del repositorio** haciendo clic en el botón "Fork" en la parte superior derecha de la página de GitHub.
2. **Clona tu Fork localmente:**
   ```bash
   git clone https://github.com/Eduardo-ci/celarpass_pro.git
   cd CelarPass_Pro
   ```
3. **Crea un entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   ```
4. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
5. **Ejecuta la aplicación** para verificar que todo funciona:
   ```bash
   python main.py
   ```

## 📐 Estándares de Código

* **Python:** Intentamos seguir las convenciones de PEP 8. Asegúrate de que tu código sea legible, mantenga el estilo existente y utilice *Type Hints* (anotaciones de tipo) siempre que sea posible.
* **UI (PySide6):** Los cambios en la interfaz gráfica se realizan a través de los archivos `.ui` ubicados en la carpeta `/ui`. Utiliza *Qt Designer* para modificarlos.
* **Seguridad:** Dado que es una aplicación criptográfica, cualquier cambio en `celarpass_core` será revisado exhaustivamente. Evita el uso de módulos inseguros como `random` para la generación de secretos, usando siempre `secrets` de la biblioteca estándar o abstracciones aprobadas por la arquitectura actual.

## 🌍 Traducciones (Localización)

CelarPass utiliza el sistema de traducción de Qt (archivos `.ts` y `.qm`). 
Para actualizar o crear una traducción:

1. Modifica los archivos `.ui` o el código en `main.py`.
2. Ejecuta el script de actualización de traducciones para extraer las nuevas cadenas a los archivos `.ts`:
   ```bash
   ./update_translations.sh
   ```
3. Abre el archivo `.ts` correspondiente (ej. `resources/lang/lang_en.ts`) utilizando la herramienta **Qt Linguist** (incluida en las herramientas de desarrollo de Qt).
4. Realiza las traducciones, guarda el archivo y vuelve a ejecutar `./update_translations.sh` para compilar los archivos `.qm`.

## 🔄 Flujo de Pull Requests (PR)

1. Crea una rama para tu característica o corrección:
   ```bash
   git checkout -b feature/mi-nueva-caracteristica
   # o
   git checkout -b fix/correccion-de-error
   ```
2. Realiza tus cambios y asegúrate de que la aplicación se ejecuta correctamente.
3. Haz *commits* claros y descriptivos.
4. Sube tus cambios a tu fork:
   ```bash
   git push origin feature/mi-nueva-caracteristica
   ```
5. Abre un **Pull Request** desde tu fork hacia la rama `main` del repositorio original.
6. Describe detalladamente qué cambios has realizado y qué *Issue* resuelven (si aplica).

## 📄 Licencia y Contribuciones

Al enviar un Pull Request a CelarPass, aceptas que tus contribuciones se licenciarán bajo la **GNU AGPLv3**, al igual que el resto del proyecto. Esto asegura que el código y tus mejoras permanezcan libres y abiertos para siempre.