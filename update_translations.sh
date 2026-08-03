#!/bin/bash

# Este script actualiza los archivos de traducción para CelarPass
# Extrae cadenas de Python y archivos UI, y compila los .qm

echo "🔍 Buscando cadenas a traducir y actualizando archivos .ts..."

# Usamos pyside6-lupdate para actualizar los archivos .ts desde el código fuente y las interfaces de usuario
pyside6-lupdate . main.py celarpass_core/*.py -ts resources/lang/lang_en.ts resources/lang/lang_es.ts resources/lang/lang_pt.ts

echo "⚙️  Generando/Actualizando archivos binarios compilados (.qm)..."

# Usamos pyside6-lrelease para compilar los archivos .ts a archivos .qm listos para la aplicación
pyside6-lrelease resources/lang/lang_en.ts resources/lang/lang_es.ts resources/lang/lang_pt.ts

echo "✅ ¡Traducciones actualizadas correctamente!"
