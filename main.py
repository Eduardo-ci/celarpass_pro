import sys
import os
import string
import secrets
import time
import logging
import json
import uuid
import glob
from typing import List, Tuple, Optional, Dict, Any

# --- DEPENDENCIAS OPCIONALES/NUEVAS ---
try:
    import argon2
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False

try:
    import qrcode
    import io
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import g19_rc
except ImportError:
    pass  # Ignorar si no está compilado el archivo de recursos aún

# --- INTEGRACIÓN DBUS (solo Linux/KDE para Klipper) ---
_HAS_DBUS = False
if sys.platform != "win32":
    try:
        from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBus
        _HAS_DBUS = True
    except ImportError:
        pass

from platformdirs import user_config_dir
from cryptography.fernet import Fernet

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QProgressBar, 
    QMessageBox, QInputDialog, QFileDialog, QDialog,
    QGroupBox, QRadioButton, QVBoxLayout, QHBoxLayout,
    QButtonGroup, QPushButton, QLabel, QSystemTrayIcon
)
from PySide6.QtCore import (
    QLocale, QTranslator, Slot, QIODevice, QFile, QSettings, 
    QCoreApplication, QObject, Signal, QRunnable, QThreadPool, QEvent, QUrl, QTimer, QMimeData
)
from PySide6.QtGui import QClipboard, QPixmap, QImage, QDesktopServices
from PySide6.QtUiTools import QUiLoader

from cipherpass_core.generators import PasswordEngine, TOTPEngine, DEFAULT_SYMBOLS
from cipherpass_core.analyzers import StrengthAnalyzer
from cipherpass_core.crypto_vault import VaultExporter
from cipherpass_core.hibp import HIBPClient

__all__ = [
    "SettingsManager",
    "ComplianceManager",
    "CryptoManager",
    "HIBPSignals",
    "HIBPWorker",
    "QRHelper",
    "CipherPassApp",
    "resource_path",
    "VERSION"
]

# --- CONFIGURACIÓN DE LOGGING ---
# SEGURIDAD (M-03): En producción (ejecutable compilado), se usa nivel WARNING
# para evitar filtrar rutas del sistema de archivos en logs compartidos.
_log_level = logging.WARNING if getattr(sys, 'frozen', False) else logging.INFO
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# --- CONSTANTES ---
VERSION = "1.0.4"

# --- GESTIÓN DE RUTAS ---
def resource_path(relative_path: str) -> str:
    """Obtiene la ruta absoluta al recurso, funciona para dev y para PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- GESTIÓN DE CONFIGURACIÓN ---
class SettingsManager:
    """Gestiona la persistencia de configuraciones de la aplicación."""
    def __init__(self) -> None:
        self.settings = QSettings("CipherPass", "CipherPassApp")

    def get_language(self) -> str:
        return str(self.settings.value("language", "es")).strip()

    def set_language(self, lang_code: str) -> None:
        self.settings.setValue("language", lang_code.strip())

    # --- Opciones de Seguridad ---
    def get_field_clear_mode(self) -> str:
        """Modo de limpieza de campos: 'tab_change', 'on_exit', 'timeout'."""
        return str(self.settings.value("security/field_clear_mode", "tab_change")).strip()

    def set_field_clear_mode(self, mode: str) -> None:
        self.settings.setValue("security/field_clear_mode", mode.strip())

    def get_clipboard_clear_mode(self) -> str:
        """Modo de limpieza del portapapeles: 'full_always', 'current_only', 'history_on_exit'."""
        return str(self.settings.value("security/clipboard_clear_mode", "current_only")).strip()

    def set_clipboard_clear_mode(self, mode: str) -> None:
        self.settings.setValue("security/clipboard_clear_mode", mode.strip())

# --- COMPLIANCE MANAGER ---
class ComplianceManager:
    """Administra los preajustes normativos de seguridad."""
    _PRESETS = None

    @classmethod
    def _load_presets(cls) -> None:
        if cls._PRESETS is not None:
            return
            
        rules_path = resource_path(os.path.join("resources", "compliance_rules.json"))
        
        # Esquema esperado para cada normativa
        expected_schema = {
            "length": int, "upper": bool, "lower": bool, 
            "nums": bool, "syms": bool, "min_n": int, "min_s": int
        }
        
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                raw_presets = json.load(f)
                
            if not isinstance(raw_presets, dict):
                raise ValueError("El archivo JSON debe contener un objeto/diccionario en su raíz.")

            valid_presets = {}
            for preset_name, rules in raw_presets.items():
                if not isinstance(rules, dict):
                    continue
                # Verificar que existan todas las llaves y coincidan en tipo
                if all(k in rules and isinstance(rules[k], t) for k, t in expected_schema.items()):
                    valid_presets[preset_name] = rules
                else:
                    logging.warning(f"Ignorando preset '{preset_name}' por formato inválido o llaves faltantes.")
                    
            if not valid_presets:
                raise ValueError("No se encontraron presets válidos en el archivo.")
                
            cls._PRESETS = valid_presets
            
        except Exception as e:
            logging.error(f"Error cargando o validando {rules_path}: {e}. Usando valores predeterminados.")
            # Fallback seguro
            cls._PRESETS = {
                "Active Directory": {"length": 14, "upper": True, "lower": True, "nums": True, "syms": True, "min_n": 1, "min_s": 1},
                "AWS IAM": {"length": 16, "upper": True, "lower": True, "nums": True, "syms": True, "min_n": 1, "min_s": 1},
                "PCI-DSS": {"length": 12, "upper": True, "lower": True, "nums": True, "syms": True, "min_n": 1, "min_s": 1},
                "NIST 800-63B": {"length": 15, "upper": True, "lower": True, "nums": False, "syms": False, "min_n": 0, "min_s": 0}
            }

    @classmethod
    def get_preset_rules(cls, preset_name: str) -> Optional[Dict[str, Any]]:
        cls._load_presets()
        return cls._PRESETS.get(preset_name)

# --- GESTOR CRIPTOGRÁFICO ---
class CryptoManager:
    """Gestiona la clave de cifrado maestra local para los diccionarios Diceware.
    
    Esta clase se encarga de crear o recuperar una clave simétrica de Fernet 
    almacenada en el directorio de configuración del usuario.
    """
    @staticmethod
    def get_cipher_suite() -> Fernet:
        """Obtiene la suite criptográfica para cifrado y descifrado local.
        
        Returns:
            Fernet: Instancia de Fernet inicializada con la clave local.
        """
        config_dir = user_config_dir("CipherPass", "CipherPassApp")
        os.makedirs(config_dir, exist_ok=True)
        key_file = os.path.join(config_dir, "secret.key")
        
        try:
            if os.path.exists(key_file):
                with open(key_file, "rb") as f:
                    return Fernet(f.read().strip())
            else:
                new_key = Fernet.generate_key()
                with open(key_file, "wb") as f:
                    f.write(new_key)
                return Fernet(new_key)
            
        except Exception as e:
            logging.error(f"Error crítico al gestionar la clave: {e}")
            # SEGURIDAD (M-02): NO continuar con una clave efímera.
            # Una clave efímera se pierde al cerrar la app, haciendo ilegibles
            # todos los archivos cifrados previamente sin ningún aviso al usuario.
            raise RuntimeError(
                f"No se puede inicializar la clave de cifrado local en '{key_file}'. "
                f"Verifica los permisos del directorio de configuración. Error: {e}"
            ) from e

# --- WORKER ASÍNCRONO PARA HIBP ---
class HIBPSignals(QObject):
    finished = Signal(int, str)

class HIBPWorker(QRunnable):
    """Consulta la API de Pwned Passwords mediante K-Anonymity sin bloquear la UI."""
    def __init__(self, password: str):
        super().__init__()
        self.password = password
        self.signals = HIBPSignals()

    @Slot()
    def run(self):
        count, error_msg = HIBPClient.check_password(self.password)
        self.signals.finished.emit(count, error_msg)
        del self.password

# --- UI HELPER QR ---
class QRHelper:
    @staticmethod
    def generate_pixmap(uri: str, size: int = 200) -> Optional[QPixmap]:
        if not HAS_QRCODE: return None
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            byte_io = io.BytesIO()
            img.save(byte_io, 'PNG')
            byte_io.seek(0)
            
            qimg = QImage()
            qimg.loadFromData(byte_io.read())
            return QPixmap.fromImage(qimg).scaled(size, size)
        except Exception as e:
            logging.error(f"Fallo al generar QR: {e}")
            return None


# --- INTERFAZ PRINCIPAL ---
class SecuritySettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("CipherPassApp", "Opciones de Seguridad"))
        self.setModal(True)
        self.settings = SettingsManager()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.fields_group = QGroupBox(QCoreApplication.translate("CipherPassApp", "Limpieza de campos sensibles"))
        fields_layout = QVBoxLayout()
        
        self.rb_field_tab = QRadioButton(QCoreApplication.translate("CipherPassApp", "Limpiar al cambiar de pestaña (Recomendado)"))
        lbl_field_tab = QLabel(QCoreApplication.translate("CipherPassApp", "Máxima seguridad. Los campos generados se borran automáticamente al cambiar de pestaña."))
        lbl_field_tab.setWordWrap(True)
        lbl_field_tab.setStyleSheet("color: gray; margin-bottom: 10px; margin-left: 20px;")
        
        self.rb_field_exit = QRadioButton(QCoreApplication.translate("CipherPassApp", "Limpiar solo al cerrar la aplicación"))
        lbl_field_exit = QLabel(QCoreApplication.translate("CipherPassApp", "Mejor experiencia. Puedes volver a ver los datos generados mientras la app esté abierta.\n⚠ Los datos permanecen visibles en pantalla."))
        lbl_field_exit.setWordWrap(True)
        lbl_field_exit.setStyleSheet("color: gray; margin-bottom: 10px; margin-left: 20px;")
        
        self.rb_field_timeout = QRadioButton(QCoreApplication.translate("CipherPassApp", "Limpiar tras 60 segundos de inactividad"))
        lbl_field_timeout = QLabel(QCoreApplication.translate("CipherPassApp", "Balance entre seguridad y comodidad. Los campos se borran si no hay interacción durante 60 segundos al cambiar de pestaña."))
        lbl_field_timeout.setWordWrap(True)
        lbl_field_timeout.setStyleSheet("color: gray; margin-bottom: 10px; margin-left: 20px;")
        
        self.bg_fields = QButtonGroup(self)
        self.bg_fields.addButton(self.rb_field_tab, 0)
        self.bg_fields.addButton(self.rb_field_exit, 1)
        self.bg_fields.addButton(self.rb_field_timeout, 2)
        
        fields_layout.addWidget(self.rb_field_tab)
        fields_layout.addWidget(lbl_field_tab)
        fields_layout.addWidget(self.rb_field_exit)
        fields_layout.addWidget(lbl_field_exit)
        fields_layout.addWidget(self.rb_field_timeout)
        fields_layout.addWidget(lbl_field_timeout)
        self.fields_group.setLayout(fields_layout)
        
        self.clip_group = QGroupBox(QCoreApplication.translate("CipherPassApp", "Limpieza del portapapeles"))
        clip_layout = QVBoxLayout()
        
        self.rb_clip_full = QRadioButton(QCoreApplication.translate("CipherPassApp", "Borrar contenido e historial siempre"))
        lbl_clip_full = QLabel(QCoreApplication.translate("CipherPassApp", "Al copiar y al cerrar, se limpia el contenido Y todo el historial del portapapeles.\n⚠ Borra también lo que hayas copiado desde otras aplicaciones."))
        lbl_clip_full.setWordWrap(True)
        lbl_clip_full.setStyleSheet("color: gray; margin-bottom: 10px; margin-left: 20px;")
        
        self.rb_clip_current = QRadioButton(QCoreApplication.translate("CipherPassApp", "Solo borrar el contenido actual (Recomendado)"))
        lbl_clip_current = QLabel(QCoreApplication.translate("CipherPassApp", "Limpia el último elemento copiado tras 15s, sin tocar el historial del portapapeles.\n⚠ Contraseñas anteriores pueden quedar en el historial del gestor de portapapeles."))
        lbl_clip_current.setWordWrap(True)
        lbl_clip_current.setStyleSheet("color: gray; margin-bottom: 10px; margin-left: 20px;")
        
        self.rb_clip_history = QRadioButton(QCoreApplication.translate("CipherPassApp", "Borrar historial solo al cerrar"))
        lbl_clip_history = QLabel(QCoreApplication.translate("CipherPassApp", "El contenido activo se limpia tras 15s. El historial completo se purga al cerrar la aplicación."))
        lbl_clip_history.setWordWrap(True)
        lbl_clip_history.setStyleSheet("color: gray; margin-bottom: 10px; margin-left: 20px;")
        
        self.bg_clip = QButtonGroup(self)
        self.bg_clip.addButton(self.rb_clip_full, 0)
        self.bg_clip.addButton(self.rb_clip_current, 1)
        self.bg_clip.addButton(self.rb_clip_history, 2)
        
        clip_layout.addWidget(self.rb_clip_full)
        clip_layout.addWidget(lbl_clip_full)
        clip_layout.addWidget(self.rb_clip_current)
        clip_layout.addWidget(lbl_clip_current)
        clip_layout.addWidget(self.rb_clip_history)
        clip_layout.addWidget(lbl_clip_history)
        self.clip_group.setLayout(clip_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_accept = QPushButton(QCoreApplication.translate("CipherPassApp", "Aceptar"))
        self.btn_cancel = QPushButton(QCoreApplication.translate("CipherPassApp", "Cancelar"))
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_accept)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addWidget(self.fields_group)
        layout.addWidget(self.clip_group)
        layout.addLayout(btn_layout)
        
        self.btn_accept.clicked.connect(self.save_settings)
        self.btn_cancel.clicked.connect(self.reject)
        self.resize(500, 550)
        
    def load_settings(self):
        fm = self.settings.get_field_clear_mode()
        if fm == "timeout":
            self.rb_field_timeout.setChecked(True)
        elif fm == "on_exit":
            self.rb_field_exit.setChecked(True)
        else:
            self.rb_field_tab.setChecked(True)
            
        cm = self.settings.get_clipboard_clear_mode()
        if cm == "full_always":
            self.rb_clip_full.setChecked(True)
        elif cm == "current_only":
            self.rb_clip_current.setChecked(True)
        else:
            self.rb_clip_history.setChecked(True)
            
    def save_settings(self):
        if self.rb_field_timeout.isChecked():
            self.settings.set_field_clear_mode("timeout")
        elif self.rb_field_exit.isChecked():
            self.settings.set_field_clear_mode("on_exit")
        else:
            self.settings.set_field_clear_mode("tab_change")
            
        if self.rb_clip_full.isChecked():
            self.settings.set_clipboard_clear_mode("full_always")
        elif self.rb_clip_current.isChecked():
            self.settings.set_clipboard_clear_mode("current_only")
        else:
            self.settings.set_clipboard_clear_mode("history_on_exit")
            
        self.accept()


class CipherPassApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = SettingsManager()
        self.engine = PasswordEngine(cipher_suite=CryptoManager.get_cipher_suite())
        self.vault_exporter = VaultExporter()
        self.threadpool = QThreadPool()
        
        self.current_locale = QLocale(self.settings.get_language())
        self.translator = QTranslator()
        self.ui = None
        
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setSingleShot(True)
        self._clipboard_timer.timeout.connect(lambda: self._perform_clipboard_clear(show_msg=False))
        
        self._field_clear_timer = QTimer(self)
        self._field_clear_timer.setSingleShot(True)
        self._field_clear_timer.timeout.connect(self._clear_pending_fields)
        self._pending_clear_widgets = []
        
        self._clipboard_secret = ""
        
        self.init_ui()

    def init_ui(self) -> None:
        self.load_translation(self.current_locale.name().split("_")[0])
        self.load_ui_file()
        if self.ui:
            self.setWindowTitle("CipherPass")
            self.show()

    def _secure_clear_line_edit(self, widget: QLineEdit) -> None:
        """Sobrescribe buffer C++ con ceros y vacía."""
        text_len = len(widget.text())
        if text_len > 0:
            widget.setText("0" * text_len)
            widget.clear()

    def _secure_clear_text_edit(self, widget) -> None:
        """Sobrescribe, vacía, y destruye undo stack."""
        text_len = len(widget.toPlainText())
        if text_len > 0:
            widget.setPlainText("0" * text_len)
            widget.clear()
        widget.setUndoRedoEnabled(False)
        widget.setUndoRedoEnabled(True)

    def _clear_pending_fields(self):
        for widget in self._pending_clear_widgets:
            if isinstance(widget, QLineEdit):
                self._secure_clear_line_edit(widget)
            else:
                self._secure_clear_text_edit(widget)
        self._pending_clear_widgets.clear()

    def _clear_klipper_history(self) -> None:
        if _HAS_DBUS:
            try:
                msg = QDBusMessage.createMethodCall(
                    "org.kde.klipper", "/klipper", "org.kde.klipper.klipper", "clearClipboardHistory"
                )
                QDBusConnection.sessionBus().call(msg, QDBus.CallMode.NoBlock)
            except Exception as e:
                logging.warning(f"Error al limpiar Klipper: {e}")

    def load_translation(self, lang_code: str) -> None:
        QApplication.instance().removeTranslator(self.translator)
        translation_path = resource_path(os.path.join("resources", "lang"))
        if self.translator.load(f"lang_{lang_code}.qm", translation_path):
            QApplication.instance().installTranslator(self.translator)
            logging.info(f"Traducción cargada: {lang_code}")
        else:
            logging.warning(f"No se pudo cargar la traducción para: {lang_code}")

    def load_ui_file(self) -> None:
        ui_file_path = resource_path(os.path.join("ui", "main.ui"))
        
        if not os.path.exists(ui_file_path):
            logging.error(f"UI {ui_file_path} no encontrada.")
            return

        loader = QUiLoader()
        file = QFile(ui_file_path)
        if not file.open(QIODevice.ReadOnly):
            logging.error(f"Imposible abrir archivo UI: {ui_file_path}")
            return

        self.ui = loader.load(file)
        file.close()

        if not self.ui:
            logging.error(f"Fallo al construir UI: {loader.errorString()}")
            return

        self.setCentralWidget(self.ui)
        icon = self.ui.windowIcon()
        if not icon.isNull():
            self.setWindowIcon(icon)
            
        lang_code = self.current_locale.name().split("_")[0]
        filepath = resource_path(os.path.join("resources", "dic", f"diceware_{lang_code}.txt"))
        if not os.path.exists(filepath):
            filepath = resource_path(os.path.join("resources", "dic", "diceware_en.txt"))
        self.engine.load_diceware(filepath)
        self.connect_ui_elements()

    def get_clean_language_name(self, code: str) -> str:
        # Evitar regionalismos de QLocale (ej. "American English" -> "English")
        clean_names = {
            "es": "Español",
            "en": "English",
            "pt": "Português",
            "fr": "Français",
            "it": "Italiano",
            "de": "Deutsch"
        }
        if code in clean_names:
            return clean_names[code]
        name = QLocale(code).nativeLanguageName() or code.upper()
        name = name.split("(")[0].strip() # Remover región si la tiene
        return name[0].upper() + name[1:] if name else code.upper()

    def connect_ui_elements(self) -> None:
        # 1. Idioma
        self.ui.comboBox_idioma.blockSignals(True)
        self.ui.comboBox_idioma.clear()
        
        self.lbl_copy_feedback = QLabel(QCoreApplication.translate("CipherPassApp", "✓ Copiado seguro, se borrará en 15 segundos"), self.ui)
        self.lbl_copy_feedback.setStyleSheet("color: #198754; margin-left: 10px; font-weight: bold;")
        self.lbl_copy_feedback.hide()
        
        # Buscar recursivamente el layout exacto que contiene el comboBox
        parent_widget = self.ui.comboBox_idioma.parentWidget()
        
        def find_layout_for_widget(layout, target_widget):
            if not layout: return None
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget() == target_widget:
                    return layout
                elif item.layout():
                    found = find_layout_for_widget(item.layout(), target_widget)
                    if found: return found
            return None
            
        target_layout = None
        if parent_widget and parent_widget.layout():
            target_layout = find_layout_for_widget(parent_widget.layout(), self.ui.comboBox_idioma)
            
        if target_layout:
            idx = target_layout.indexOf(self.ui.comboBox_idioma)
            target_layout.insertWidget(idx + 1, self.lbl_copy_feedback)
        else:
            self.lbl_copy_feedback.setParent(self.ui.comboBox_idioma.parentWidget())
        
        lang_dir = resource_path(os.path.join("resources", "lang"))
        lang_map_dynamic = {}
        for lf in glob.glob(os.path.join(lang_dir, "lang_*.qm")):
            code = os.path.basename(lf).replace("lang_", "").replace(".qm", "")
            native_name = self.get_clean_language_name(code)
            lang_map_dynamic[native_name] = code
            
        if not lang_map_dynamic:
            lang_map_dynamic["Español"] = "es"
            
        for name in sorted(lang_map_dynamic.keys()):
            self.ui.comboBox_idioma.addItem(name, lang_map_dynamic[name])
            
        current_code = self.current_locale.name().split("_")[0]
        idx = self.ui.comboBox_idioma.findData(current_code)
        if idx != -1: self.ui.comboBox_idioma.setCurrentIndex(idx)
        self.ui.comboBox_idioma.blockSignals(False)
        self.ui.comboBox_idioma.currentIndexChanged.connect(self.change_language)

        # Limpieza de memoria al cambiar de pestaña
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)

        # 2. Generador Contraseña Original
        spinboxes = [self.ui.spinBox_longitud, self.ui.spinBox_min_numeros, self.ui.spinBox_min_especiales]
        for w in spinboxes:
            w.valueChanged.connect(self.validate_spinbox_contrasena)
            w.valueChanged.connect(self.update_password_strength)
        checkboxes = [
            self.ui.checkBox_mayusculas, self.ui.checkBox_minusculas,
            self.ui.checkBox_numeros, self.ui.checkBox_simbolos, self.ui.checkBox_evitar_ambiguos
        ]
        for chk in checkboxes:
            chk.stateChanged.connect(self.update_password_strength)
            
        self.ui.btn_generar_contrasena.clicked.connect(self.generate_password_ui)
        self.ui.btn_copiar_contrasena.clicked.connect(lambda: self.copy_to_clipboard(self.ui.lineEdit_contrasena))
        self.update_password_strength()

        # 3. Frase & Usuario Original
        self.ui.btn_generar_frase.clicked.connect(self.generate_passphrase_ui)
        self.ui.btn_copiar_frase.clicked.connect(lambda: self.copy_to_clipboard(self.ui.lineEdit_frase))
        
        self.ui.comboBox_tipo_usuario.setCurrentIndex(1)
        self.ui.checkBox_usuario_servicio.stateChanged.connect(self.toggle_service_tag_field)
        self.toggle_service_tag_field(self.ui.checkBox_usuario_servicio.isChecked())
        self.ui.btn_generar_usuario.clicked.connect(self.generate_username_ui)
        self.ui.btn_copiar_usuario.clicked.connect(lambda: self.copy_to_clipboard(self.ui.lineEdit_usuario))

        # 4. Validar Pasivo Original
        self.ui.lineEdit_validar_pass.setEchoMode(QLineEdit.Password)
        self.ui.btn_validar_ver.setChecked(False)
        self.ui.btn_validar_ver.toggled.connect(self.toggle_password_visibility)
        self.ui.lineEdit_validar_pass.textChanged.connect(self.analyze_password_strength)

        # 5. Integraciones PRO (Tokens, Compliance, HIBP, Vault, TOTP)
        self.ui.btn_generar_token.clicked.connect(self.generate_token_ui)
        self.ui.btn_copiar_token.clicked.connect(lambda: self.copy_to_clipboard(self.ui.lineEdit_token_resultado))
        
        # Cargar dinámicamente presets de Compliance respetando el elemento 0 ('Modo manual' traducido por PySide6)
        self.ui.comboBox_compliance.blockSignals(True)
        while self.ui.comboBox_compliance.count() > 1:
            self.ui.comboBox_compliance.removeItem(1)
        ComplianceManager._load_presets()
        if ComplianceManager._PRESETS:
            self.ui.comboBox_compliance.addItems(list(ComplianceManager._PRESETS.keys()))
        self.ui.comboBox_compliance.blockSignals(False)
        
        self.ui.comboBox_compliance.currentIndexChanged.connect(self.apply_compliance_preset)
        self.ui.btn_manual_mode.clicked.connect(self.enable_manual_mode)
        self.ui.btn_hibp_check.clicked.connect(self.check_hibp)
        self.ui.btn_hibp_check.setEnabled(self.ui.checkBox_hibp.isChecked())
        self.ui.checkBox_hibp.toggled.connect(self.ui.btn_hibp_check.setEnabled)
        self.ui.btn_export_vault.clicked.connect(self.export_vault_ui)
        self.ui.btn_import_vault.clicked.connect(self.import_vault_ui)
        self.ui.btn_browse_vault.clicked.connect(self.browse_vault_file)
        self.ui.btn_generar_totp.clicked.connect(self.generate_totp_ui)
        self.ui.btn_copiar_totp.clicked.connect(lambda: self.copy_to_clipboard(self.ui.lineEdit_totp_secret))
        self.ui.btn_copiar_uri.clicked.connect(lambda: self.copy_to_clipboard(self.ui.lineEdit_totp_uri))
        self.ui.btn_save_qr.clicked.connect(self.save_qr_ui)

        self.ui.btn_generar_totp.setEnabled(False)
        self.ui.btn_save_qr.setEnabled(False)
        self.ui.lineEdit_service_name.textChanged.connect(self.validate_totp_inputs)
        self.ui.lineEdit_account_name.textChanged.connect(self.validate_totp_inputs)
        
        # Configurar menú superior
        self._setup_menus()

    def _setup_menus(self) -> None:
        """Configura la barra de menús superior."""
        menu_bar = self.menuBar()
        menu_bar.clear()  # Evitar duplicados al cambiar de idioma
        
        # Textos Traducibles
        archivo_text = QCoreApplication.translate("CipherPassApp", "Archivo")
        salir_text = QCoreApplication.translate("CipherPassApp", "Salir")
        
        herramientas_text = QCoreApplication.translate("CipherPassApp", "Herramientas")
        limpiar_portapapeles_text = QCoreApplication.translate("CipherPassApp", "Limpiar Portapapeles")
        
        opciones_text = QCoreApplication.translate("CipherPassApp", "Opciones")
        idioma_text = QCoreApplication.translate("CipherPassApp", "Idioma")
        
        ayuda_text = QCoreApplication.translate("CipherPassApp", "Ayuda")
        docs_text = QCoreApplication.translate("CipherPassApp", "Documentación en línea")
        acerca_text = QCoreApplication.translate("CipherPassApp", "Acerca de CipherPass...")
        seguridad_text = QCoreApplication.translate("CipherPassApp", "Seguridad...")
        
        # --- 1. Menú Archivo ---
        file_menu = menu_bar.addMenu(archivo_text)
        quit_action = file_menu.addAction(salir_text)
        quit_action.triggered.connect(self.quit_app_action)
        
        # --- 2. Menú Herramientas ---
        tools_menu = menu_bar.addMenu(herramientas_text)
        clear_clip_action = tools_menu.addAction(limpiar_portapapeles_text)
        clear_clip_action.triggered.connect(self.clear_clipboard_action)
        
        # --- 3. Menú Opciones ---
        options_menu = menu_bar.addMenu(opciones_text)
        security_action = options_menu.addAction(seguridad_text)
        security_action.triggered.connect(self._open_security_settings)
        options_menu.addSeparator()
        
        lang_menu = options_menu.addMenu(idioma_text)
        
        lang_dir = resource_path(os.path.join("resources", "lang"))
        for lf in sorted(glob.glob(os.path.join(lang_dir, "lang_*.qm"))):
            code = os.path.basename(lf).replace("lang_", "").replace(".qm", "")
            native_name = self.get_clean_language_name(code)
            action = lang_menu.addAction(native_name)
            action.triggered.connect(lambda checked=False, c=code: self.change_language_code(c))
        
        # --- 4. Menú Ayuda ---
        help_menu = menu_bar.addMenu(ayuda_text)
        docs_action = help_menu.addAction(docs_text)
        docs_action.triggered.connect(self.open_documentation_action)
        help_menu.addSeparator()
        about_action = help_menu.addAction(acerca_text)
        about_action.triggered.connect(self.show_about_dialog)

    @Slot()
    def _open_security_settings(self):
        dialog = SecuritySettingsDialog(self)
        dialog.exec()

    def _purge_all_sensitive_data(self) -> None:
        self._clipboard_timer.stop()
        self._field_clear_timer.stop()
        
        sensibles = [
            self.ui.lineEdit_contrasena,
            self.ui.lineEdit_frase,
            self.ui.lineEdit_usuario,
            self.ui.lineEdit_token_resultado,
            self.ui.lineEdit_totp_secret,
            self.ui.lineEdit_totp_uri,
            self.ui.lineEdit_validar_pass
        ]
        for w in sensibles:
            if w: self._secure_clear_line_edit(w)
            
        if self.ui.textEdit_import_data: self._secure_clear_text_edit(self.ui.textEdit_import_data)
        if self.ui.textEdit_export_data: self._secure_clear_text_edit(self.ui.textEdit_export_data)
        
        if hasattr(self.ui, 'label_qr') and self.ui.label_qr.pixmap():
            self.ui.label_qr.clear()
            
        self._perform_clipboard_clear(show_msg=False)
        
        mode = self.settings.get_clipboard_clear_mode()
        if mode in ("full_always", "history_on_exit"):
            self._clear_klipper_history()

    def closeEvent(self, event) -> None:
        self._purge_all_sensitive_data()
        event.accept()

    @Slot()
    def quit_app_action(self) -> None:
        self._purge_all_sensitive_data()
        QApplication.quit()

    @Slot()
    def clear_clipboard_action(self) -> None:
        self._perform_clipboard_clear(show_msg=True)

    def _perform_clipboard_clear(self, show_msg: bool = True) -> None:
        if hasattr(self, 'lbl_copy_feedback'):
            self.lbl_copy_feedback.hide()
            
        clipboard = QApplication.clipboard()
        current_text = clipboard.text()
        
        # Solo borrar si el portapapeles sigue conteniendo la contraseña generada
        if current_text == self._clipboard_secret and self._clipboard_secret != "":
            clipboard.clear(QClipboard.Mode.Clipboard)
            if sys.platform != "win32" and clipboard.supportsSelection():
                clipboard.clear(QClipboard.Mode.Selection)
                
        self._clipboard_secret = ""
        mode = self.settings.get_clipboard_clear_mode()
        if mode == "full_always":
            self._clear_klipper_history()
            
        if show_msg:
            QMessageBox.information(self, 
                QCoreApplication.translate("CipherPassApp", "Portapapeles Limpio"), 
                QCoreApplication.translate("CipherPassApp", "El portapapeles ha sido borrado por seguridad.")
            )

    @Slot()
    def open_documentation_action(self) -> None:
        QDesktopServices.openUrl(QUrl("https://github.com/Eduardo-ci/cipherpass_pro"))

    @Slot(str)
    def change_language_code(self, lang_code: str) -> None:
        current = self.current_locale.name().split("_")[0]
        if lang_code and lang_code != current:
            self.current_locale = QLocale(lang_code)
            self.settings.set_language(lang_code)
            self.load_translation(lang_code)
            self.load_ui_file()

    @Slot()
    def show_about_dialog(self) -> None:
        """Muestra el diálogo de información de la aplicación."""
        estado = QCoreApplication.translate("CipherPassApp", "GNU AGPLv3 (Código Abierto)")
        version_lbl = QCoreApplication.translate("CipherPassApp", "Versión:")
        license_lbl = QCoreApplication.translate("CipherPassApp", "Licencia:")
        desc_lbl = QCoreApplication.translate("CipherPassApp", "Aplicación de código abierto diseñada para generar, validar y proteger credenciales criptográficas asegurando tu privacidad offline-first.")
        visit_lbl = QCoreApplication.translate("CipherPassApp", "Visitar el sitio web oficial")
        about_title = QCoreApplication.translate("CipherPassApp", "Acerca de CipherPass")
        
        # QMessageBox.about interpreta HTML nativamente
        texto_html = (
            f"<h2>CipherPass</h2>"
            f"<p><b>{version_lbl}</b> {VERSION}</p>"
            f"<p><b>{license_lbl}</b> {estado}</p>"
            f"<hr>"
            f"<p>{desc_lbl}</p>"
            f"<p><a href='https://www.cipherpass.com'>{visit_lbl}</a></p>"
        )
        QMessageBox.about(self, about_title, texto_html)

    # --- SLOTS ORIGINALES DE UI ---
    @Slot()
    def update_password_strength(self) -> None:
        current_pwd = self.ui.lineEdit_contrasena.text()
        if current_pwd and current_pwd != "Selecciona opciones":
            val, color, msg_key, _, _ = StrengthAnalyzer.get_unified_metrics(current_pwd)
            msg = QCoreApplication.translate("CipherPassApp", msg_key)
        else:
            val, color, msg_key = StrengthAnalyzer.calculate_entropy_preview(
                self.ui.spinBox_longitud.value(), self.ui.checkBox_mayusculas.isChecked(),
                self.ui.checkBox_minusculas.isChecked(), self.ui.checkBox_numeros.isChecked(),
                self.ui.checkBox_simbolos.isChecked()
            )
            msg = QCoreApplication.translate("CipherPassApp", msg_key)
        self.ui.progressBar_fortaleza.setValue(val)
        self.ui.progressBar_fortaleza.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")
        self.ui.progressBar_fortaleza.setFormat(f"{msg} ({val}%)")

    @Slot()
    def analyze_password_strength(self) -> None:
        pwd = self.ui.lineEdit_validar_pass.text()
        if not pwd:
            self.reset_validar_ui()
            return
        val, color, msg_key, crack_seconds, warning_key = StrengthAnalyzer.get_unified_metrics(pwd)
        
        msg = QCoreApplication.translate("CipherPassApp", msg_key)
        warning = QCoreApplication.translate("CipherPassApp", warning_key) if warning_key else ""
        time_text = self._format_crack_time(crack_seconds)
        
        if warning: msg += f" ({warning})"
        time_text_prefix = QCoreApplication.translate("CipherPassApp", "Tiempo estimado:")
        self.ui.label_validar_tiempo.setText(f"{time_text_prefix} {time_text}")
        self.ui.progressBar_validar.setValue(val)
        self.ui.progressBar_validar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")
        self.ui.label_validar_mensaje.setText(msg)

    def _format_crack_time(self, seconds: float) -> str:
        if seconds < 1:
            return QCoreApplication.translate("CipherPassApp", "Instantáneo")
        if seconds < 60:
            return QCoreApplication.translate("CipherPassApp", f"{int(seconds)} s")
        if seconds < 3600:
            return QCoreApplication.translate("CipherPassApp", f"{int(seconds/60)} min")
        if seconds < 86400:
            return QCoreApplication.translate("CipherPassApp", f"{int(seconds/3600)} h")
        if seconds < 31536000:
            return QCoreApplication.translate("CipherPassApp", f"{int(seconds/86400)} días")
        if seconds < 315360000:
            return QCoreApplication.translate("CipherPassApp", f"{int(seconds/31536000)} años")
        return QCoreApplication.translate("CipherPassApp", "Siglos")

    @Slot(bool)
    def toggle_service_tag_field(self, checked: bool) -> None:
        self.ui.lineEdit_usuario_servicio.setEnabled(checked)

    @Slot(bool)
    def toggle_password_visibility(self, checked: bool) -> None:
        self.ui.lineEdit_validar_pass.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    @Slot(int)
    def change_language(self, index: int) -> None:
        lang_code = self.ui.comboBox_idioma.itemData(index)
        current = self.current_locale.name().split("_")[0]
        if lang_code and lang_code != current:
            self.current_locale = QLocale(lang_code)
            self.settings.set_language(lang_code)
            self.load_translation(lang_code)
            self.load_ui_file()

    @Slot(int)
    def on_tab_changed(self, index: int) -> None:
        """Sobrescribe y limpia los datos sensibles cuando se cambia de pestaña."""
        current_widget = self.ui.tabWidget.widget(index)
        
        if current_widget != self.ui.tab_validar:
            self._secure_clear_line_edit(self.ui.lineEdit_validar_pass)
            self.reset_validar_ui()
            if hasattr(self.ui, 'label_hibp_resultado'):
                self.ui.label_hibp_resultado.setVisible(False)
            if hasattr(self.ui, 'progressBar_hibp'):
                self.ui.progressBar_hibp.setVisible(False)

        if current_widget != self.ui.tab_vault:
            self._secure_clear_text_edit(self.ui.textEdit_import_data)
            self._secure_clear_text_edit(self.ui.textEdit_export_data)
            self.ui.label_vault_estado.clear()

        # Otras pestañas según configuración
        mode = self.settings.get_field_clear_mode()
        sensibles = [
            self.ui.lineEdit_contrasena,
            self.ui.lineEdit_frase,
            self.ui.lineEdit_usuario,
            self.ui.lineEdit_token_resultado,
            self.ui.lineEdit_totp_secret,
            self.ui.lineEdit_totp_uri
        ]
        
        if mode == "tab_change":
            for w in sensibles:
                if w: self._secure_clear_line_edit(w)
        elif mode == "timeout":
            self._pending_clear_widgets.extend([w for w in sensibles if w])
            # Evitar duplicados
            self._pending_clear_widgets = list(set(self._pending_clear_widgets))
            self._field_clear_timer.start(60000)

    def validate_spinbox_contrasena(self) -> None:
        length = self.ui.spinBox_longitud.value()
        req = self.ui.spinBox_min_numeros.value() + self.ui.spinBox_min_especiales.value()
        if req > length:
            self.ui.spinBox_longitud.setValue(req)

    @Slot()
    def validate_totp_inputs(self) -> None:
        has_text = bool(self.ui.lineEdit_service_name.text().strip() and self.ui.lineEdit_account_name.text().strip())
        self.ui.btn_generar_totp.setEnabled(has_text)

    # --- SLOTS GENERACIÓN ---
    def generate_password_ui(self) -> None:
        self.ui.btn_generar_contrasena.setEnabled(False)
        QApplication.processEvents()
        pwd = self.engine.generate_password(
            self.ui.spinBox_longitud.value(), self.ui.spinBox_min_numeros.value(),
            self.ui.spinBox_min_especiales.value(), self.ui.checkBox_mayusculas.isChecked(),
            self.ui.checkBox_minusculas.isChecked(), self.ui.checkBox_numeros.isChecked(),
            self.ui.checkBox_simbolos.isChecked(), self.ui.checkBox_evitar_ambiguos.isChecked()
        )
        self.ui.lineEdit_contrasena.setText(pwd if pwd else QCoreApplication.translate("CipherPassApp", "Selecciona opciones"))
        self.update_password_strength()
        self.ui.btn_generar_contrasena.setEnabled(True)

    def generate_passphrase_ui(self) -> None:
        phrase = self.engine.generate_passphrase(
            self.ui.spinBox_num_palabras.value(), self.ui.checkBox_capitalizar.isChecked(),
            self.ui.checkBox_incluir_numeros.isChecked(), self.ui.lineEdit_separador.text()
        )
        self.ui.lineEdit_frase.setText(phrase if phrase else QCoreApplication.translate("CipherPassApp", "Error: Sin diccionario"))

    def generate_username_ui(self) -> None:
        username = self.engine.generate_username(
            self.ui.comboBox_tipo_usuario.currentIndex(), self.ui.lineEdit_usuario_dominio.text(),
            self.ui.lineEdit_usuario_servicio.text(), self.ui.checkBox_usuario_servicio.isChecked()
        )
        self.ui.lineEdit_usuario.setText(username)

    def reset_validar_ui(self) -> None:
        self.ui.label_validar_tiempo.setText(QCoreApplication.translate("CipherPassApp", "Tiempo estimado: -"))
        self.ui.progressBar_validar.setValue(0)
        self.ui.progressBar_validar.setStyleSheet("")
        self.ui.label_validar_mensaje.setText(QCoreApplication.translate("CipherPassApp", "Ingresa una contraseña..."))

    def copy_to_clipboard(self, widget: QLineEdit) -> None:
        text = widget.text()
        if not text or text == QCoreApplication.translate("CipherPassApp", "Selecciona opciones") or text == QCoreApplication.translate("CipherPassApp", "Error: Sin diccionario"):
            return
            
        # Guardar referencia en self para evitar recolección de basura prematura
        self._clipboard_secret = text
        self._current_mime_data = QMimeData()
        self._current_mime_data.setText(text)
        self._current_mime_data.setData("x-kde-passwordManagerHint", b"secret")
        QApplication.clipboard().setMimeData(self._current_mime_data)
        
        btn = self.sender()
        if isinstance(btn, QPushButton):
            original_style = btn.styleSheet()
            original_text = btn.text()
            btn.setStyleSheet("background-color: #198754; color: white; border-radius: 4px;")
            if original_text:
                btn.setText(QCoreApplication.translate("CipherPassApp", "¡Copiado!"))
                
            def restore_btn():
                btn.setStyleSheet(original_style)
                btn.setText(original_text)
                
            QTimer.singleShot(1500, restore_btn)
        
        is_new_copy = not self._clipboard_timer.isActive()
        self._clipboard_timer.start(15000)
        
        msg = QCoreApplication.translate("CipherPassApp", "✓ Copiado seguro, se borrará en 15 segundos")
        if hasattr(self, 'lbl_copy_feedback'):
            self.lbl_copy_feedback.setText(msg)
            self.lbl_copy_feedback.show()
        
        if is_new_copy:
            if not hasattr(self, '_tray_icon'):
                self._tray_icon = QSystemTrayIcon(self)
                self._tray_icon.setIcon(self.windowIcon())
                self._tray_icon.show()
            self._tray_icon.showMessage(
                QCoreApplication.translate("CipherPassApp", "CipherPass Pro"), msg,
                QSystemTrayIcon.MessageIcon.Information, 3000
            )

    # --- NUEVOS SLOTS PRO: Tokens, Compliance, HIBP, Vault, TOTP ---
    @Slot()
    def generate_token_ui(self) -> None:
        mode = self.ui.comboBox_token_tipo.currentIndex()
        length = self.ui.spinBox_token_length.value()
        token = self.engine.generate_api_token(mode, length)
        self.ui.lineEdit_token_resultado.setText(token)

    @Slot(int)
    def apply_compliance_preset(self, index: int) -> None:
        controls = [
            self.ui.spinBox_longitud, self.ui.checkBox_mayusculas,
            self.ui.checkBox_minusculas, self.ui.checkBox_numeros,
            self.ui.checkBox_simbolos, self.ui.spinBox_min_numeros,
            self.ui.spinBox_min_especiales, self.ui.checkBox_evitar_ambiguos
        ]
        
        if index == 0: 
            for ctrl in controls:
                ctrl.setEnabled(True)
                
            # Restaurar los valores por defecto del inicio de la aplicación
            self.ui.spinBox_longitud.blockSignals(True)
            self.ui.spinBox_longitud.setValue(14)
            self.ui.checkBox_mayusculas.setChecked(True)
            self.ui.checkBox_minusculas.setChecked(True)
            self.ui.checkBox_numeros.setChecked(True)
            self.ui.checkBox_simbolos.setChecked(True)
            self.ui.checkBox_evitar_ambiguos.setChecked(False)
            self.ui.spinBox_min_numeros.setValue(1)
            self.ui.spinBox_min_especiales.setValue(1)
            self.ui.spinBox_longitud.blockSignals(False)
            
            self.ui.label_compliance_badge.setVisible(False)
            self.update_password_strength()
            return # Modo manual
            
        preset_name = self.ui.comboBox_compliance.currentText()
        rules = ComplianceManager.get_preset_rules(preset_name)
        if not rules: return

        self.ui.spinBox_longitud.blockSignals(True)
        self.ui.spinBox_longitud.setValue(rules["length"])
        self.ui.checkBox_mayusculas.setChecked(rules["upper"])
        self.ui.checkBox_minusculas.setChecked(rules["lower"])
        self.ui.checkBox_numeros.setChecked(rules["nums"])
        self.ui.checkBox_simbolos.setChecked(rules["syms"])
        self.ui.spinBox_min_numeros.setValue(rules["min_n"])
        self.ui.spinBox_min_especiales.setValue(rules["min_s"])
        self.ui.spinBox_longitud.blockSignals(False)
        
        for ctrl in controls:
            ctrl.setEnabled(False)
            
        policy_prefix = QCoreApplication.translate("CipherPassApp", "Bloqueado por Política:")
        self.ui.label_compliance_badge.setText(f"{policy_prefix} {preset_name}")
        self.ui.label_compliance_badge.setVisible(True)
        self.update_password_strength()

    @Slot()
    def enable_manual_mode(self) -> None:
        self.ui.comboBox_compliance.setCurrentIndex(0)

    @Slot()
    def check_hibp(self) -> None:
        pwd = self.ui.lineEdit_validar_pass.text()
        if not pwd:
            QMessageBox.warning(self, QCoreApplication.translate("CipherPassApp", "Vacío"), QCoreApplication.translate("CipherPassApp", "Ingresa una contraseña para validar."))
            return

        self.ui.btn_hibp_check.setEnabled(False)
        self.ui.progressBar_hibp.setVisible(True)
        self.ui.progressBar_hibp.setMaximum(0)
        self.ui.label_hibp_resultado.setText(QCoreApplication.translate("CipherPassApp", "Consultando de forma anónima..."))
        self.ui.label_hibp_resultado.setStyleSheet("color: #fff;")
        self.ui.label_hibp_resultado.setVisible(True)

        worker = HIBPWorker(pwd)
        worker.signals.finished.connect(self.on_hibp_result)
        self.threadpool.start(worker)

    @Slot(int, str)
    def on_hibp_result(self, count: int, error_msg: str) -> None:
        self.ui.progressBar_hibp.setVisible(False)
        self.ui.btn_hibp_check.setEnabled(True)

        if count == -1:
            error_prefix = QCoreApplication.translate("CipherPassApp", "⚠️ Error:")
            self.ui.label_hibp_resultado.setText(f"{error_prefix} {error_msg}")
            self.ui.label_hibp_resultado.setStyleSheet("background-color: #333; color: #ffc107;")
        elif count == 0:
            self.ui.label_hibp_resultado.setText(QCoreApplication.translate("CipherPassApp", "✅ Excelente. Esta contraseña no aparece en brechas de datos conocidas."))
            self.ui.label_hibp_resultado.setStyleSheet("background-color: #198754; color: #fff;")
        else:
            danger_prefix = QCoreApplication.translate("CipherPassApp", "🚨 PELIGRO: Esta contraseña ha sido expuesta")
            times_suffix = QCoreApplication.translate("CipherPassApp", "veces.")
            self.ui.label_hibp_resultado.setText(f"{danger_prefix} {count:,} {times_suffix}")
            self.ui.label_hibp_resultado.setStyleSheet("background-color: #dc3545; color: #fff;")

    @Slot()
    def export_vault_ui(self) -> None:
        data = self.ui.textEdit_export_data.toPlainText()
        if not data:
            QMessageBox.warning(self, QCoreApplication.translate("CipherPassApp", "Error"), QCoreApplication.translate("CipherPassApp", "No hay datos para exportar."))
            return

        pwd, ok = QInputDialog.getText(self, QCoreApplication.translate("CipherPassApp", "Cifrar Bóveda"), QCoreApplication.translate("CipherPassApp", "Ingresa la contraseña maestra:"), QLineEdit.Password)
        if not ok or not pwd: return

        use_argon2 = (self.ui.comboBox_vault_kdf.currentIndex() == 0) and HAS_ARGON2
        try:
            enc_data = self.vault_exporter.export_vault(data, pwd, use_argon2)
            save_path, _ = QFileDialog.getSaveFileName(self, QCoreApplication.translate("CipherPassApp", "Guardar Bóveda"), "", "CipherPass Vault (*.cpv);;JSON Files (*.json)")
            if save_path:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(enc_data)
                self.ui.label_vault_estado.setText(QCoreApplication.translate("CipherPassApp", "✅ Bóveda exportada exitosamente."))
                self.ui.label_vault_estado.setStyleSheet("color: #2ecc71;")
        except Exception as e:
            error_prefix = QCoreApplication.translate("CipherPassApp", "Fallo al exportar:")
            QMessageBox.critical(self, QCoreApplication.translate("CipherPassApp", "Error Crítico"), f"{error_prefix} {e}")

    @Slot()
    def browse_vault_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, QCoreApplication.translate("CipherPassApp", "Abrir Bóveda"), "", "CipherPass Vault (*.cpv *.json);;All Files (*)")
        if file_path: self.ui.lineEdit_import_path.setText(file_path)

    @Slot()
    def import_vault_ui(self) -> None:
        path = self.ui.lineEdit_import_path.text()
        if not os.path.exists(path):
            QMessageBox.warning(self, QCoreApplication.translate("CipherPassApp", "Error"), QCoreApplication.translate("CipherPassApp", "Archivo no encontrado."))
            return

        pwd, ok = QInputDialog.getText(self, QCoreApplication.translate("CipherPassApp", "Descifrar Bóveda"), QCoreApplication.translate("CipherPassApp", "Ingresa la contraseña maestra:"), QLineEdit.Password)
        if not ok or not pwd: return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                enc_data = f.read()
            decrypted = self.vault_exporter.import_vault(enc_data, pwd)
            if decrypted:
                self.ui.textEdit_import_data.setPlainText(decrypted)
                self.ui.label_vault_estado.setText(QCoreApplication.translate("CipherPassApp", "✅ Bóveda descifrada exitosamente."))
                self.ui.label_vault_estado.setStyleSheet("color: #2ecc71;")
            else:
                QMessageBox.critical(self, QCoreApplication.translate("CipherPassApp", "Acceso Denegado"), QCoreApplication.translate("CipherPassApp", "Contraseña maestra incorrecta o archivo dañado."))
                self.ui.label_vault_estado.setText(QCoreApplication.translate("CipherPassApp", "❌ Fallo de descifrado."))
                self.ui.label_vault_estado.setStyleSheet("color: #e74c3c;")
        except Exception as e:
            error_prefix = QCoreApplication.translate("CipherPassApp", "Fallo de E/S:")
            QMessageBox.critical(self, QCoreApplication.translate("CipherPassApp", "Error"), f"{error_prefix} {e}")

    @Slot()
    def generate_totp_ui(self) -> None:
        issuer = self.ui.lineEdit_service_name.text().strip() or "Servicio"
        account = self.ui.lineEdit_account_name.text().strip() or "Usuario"
        
        secret = TOTPEngine.generate_secret()
        uri = TOTPEngine.build_uri(secret, account_name=account, issuer=issuer)

        self.ui.lineEdit_totp_secret.setText(secret)
        self.ui.lineEdit_totp_uri.setText(uri)

        if HAS_QRCODE:
            pixmap = QRHelper.generate_pixmap(uri)
            if pixmap:
                self.ui.label_qr_image.setPixmap(pixmap)
                self.ui.btn_save_qr.setEnabled(True)
        else:
            self.ui.label_qr_image.setText(QCoreApplication.translate("CipherPassApp", "Módulo 'qrcode' no instalado.\nUsa el secreto manual."))
            self.ui.btn_save_qr.setEnabled(False)

    @Slot()
    def save_qr_ui(self) -> None:
        pixmap = self.ui.label_qr_image.pixmap()
        if pixmap and not pixmap.isNull():
            save_path, _ = QFileDialog.getSaveFileName(self, QCoreApplication.translate("CipherPassApp", "Guardar Código QR"), "totp_qr.png", "Images (*.png)")
            if save_path:
                pixmap.save(save_path, "PNG")
                QMessageBox.information(self, QCoreApplication.translate("CipherPassApp", "Éxito"), QCoreApplication.translate("CipherPassApp", "Código QR guardado correctamente."))
        else:
            QMessageBox.warning(self, QCoreApplication.translate("CipherPassApp", "Error"), QCoreApplication.translate("CipherPassApp", "No hay un código QR para guardar."))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("CipherPass - Generador y validador de contraseñas criptográficas")
        print("\nUso:")
        print("  cipherpass             Inicia la aplicación gráfica")
        print("  cipherpass-cli         Inicia la interfaz de línea de comandos (CLI)")
        print("\nPara ver las opciones de la CLI, ejecuta: cipherpass-cli --help")
        sys.exit(0)

    app = QApplication(sys.argv)
    window = CipherPassApp()
    sys.exit(app.exec())