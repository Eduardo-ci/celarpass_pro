import unittest
import json
from unittest.mock import patch, MagicMock

from celarpass_core.generators import PasswordEngine, TOTPEngine
from celarpass_core.analyzers import StrengthAnalyzer
from celarpass_core.crypto_vault import VaultExporter
from celarpass_core.hibp import HIBPClient

class TestPasswordEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PasswordEngine()

    def test_generate_password_length_and_complexity(self):
        pwd = self.engine.generate_password(
            length=16, min_nums=2, min_specs=2, 
            use_upper=True, use_lower=True, use_nums=True, 
            use_syms=True, avoid_amb=False
        )
        self.assertEqual(len(pwd), 16)
        self.assertTrue(any(c.isdigit() for c in pwd), "Debe contener al menos un número")
        self.assertTrue(any(c.isupper() for c in pwd), "Debe contener al menos una mayúscula")
        # Verifica que contenga caracteres especiales de la constante
        from celarpass_core.generators import DEFAULT_SYMBOLS
        self.assertTrue(any(c in DEFAULT_SYMBOLS for c in pwd), "Debe contener símbolos")

    def test_generate_api_token(self):
        # Modo 0: URL-safe, Modo 1: Hex
        token_urlsafe = self.engine.generate_api_token(mode=0, length=32)
        self.assertTrue(len(token_urlsafe) > 32)  # La codificación base64url es más larga que los bytes puros
        
        token_hex = self.engine.generate_api_token(mode=1, length=16)
        self.assertEqual(len(token_hex), 32)  # 16 bytes = 32 caracteres hex

class TestTOTPEngine(unittest.TestCase):
    def test_generate_secret(self):
        secret = TOTPEngine.generate_secret()
        self.assertEqual(len(secret), 32)
        self.assertTrue(secret.isupper())

    def test_build_uri(self):
        uri = TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", "test@example.com")
        self.assertTrue(uri.startswith("otpauth://totp/test%40example.com?"))
        self.assertIn("secret=JBSWY3DPEHPK3PXP", uri)

class TestStrengthAnalyzer(unittest.TestCase):
    def test_entropy_preview(self):
        # Una contraseña larga con todos los caracteres debería dar máxima entropía visual
        val, color, msg = StrengthAnalyzer.calculate_entropy_preview(
            length=20, use_upper=True, use_lower=True, use_nums=True, use_syms=True
        )
        self.assertTrue(val >= 80)
        self.assertEqual(color, "#2ecc71")  # Color verde (Fuerte)

    def test_analyze_password_pattern(self):
        from celarpass_core.analyzers import analyze_password
        # Contraseña con patrón claro (diccionario + símbolo)
        results = analyze_password("Password123!")
        # Debe identificar el patrón y no sobrestimar
        self.assertTrue(results['guesses'] < 10**8, "Debe detectar el patrón débil")

    def test_analyze_password_random_short(self):
        from celarpass_core.analyzers import analyze_password
        import string, random
        # Contraseña aleatoria de 8 caracteres con todos los tipos
        chars = string.ascii_letters + string.digits + "!@#"
        pwd = ''.join(random.choice(chars) for _ in range(8))
        results = analyze_password(pwd)
        # La entropía matemática de 8 chars con pool ~65 es ~65^8 = 3.18e14
        # Si zxcvbn la marca como fuerza bruta, el fix debe sobrescribir
        if len(results['sequence']) == 1 and results['sequence'][0].get("pattern") == "bruteforce":
            self.assertTrue(results['guesses'] > 10**14, "Debe aplicar la cardinalidad matemática")

    def test_analyze_password_random_long(self):
        from celarpass_core.analyzers import analyze_password
        import string, random
        # Contraseña aleatoria de 20 caracteres con todos los tipos
        chars = string.ascii_letters + string.digits + "!@#"
        pwd = ''.join(random.choice(chars) for _ in range(20))
        results = analyze_password(pwd)
        # La entropía matemática de 20 chars con pool ~65 es ~65^20 = 1.8e36
        if len(results['sequence']) == 1 and results['sequence'][0].get("pattern") == "bruteforce":
            self.assertTrue(results['guesses'] > 10**35, "Debe aplicar la cardinalidad matemática para contraseñas largas")

class TestVaultExporter(unittest.TestCase):
    def setUp(self):
        self.vault = VaultExporter()

    def test_export_import_success(self):
        data = "my_super_secret_note"
        master_pwd = "strong_master_password_123"
        
        # Forzamos use_argon2=False para garantizar que corra en entornos sin la librería C
        exported_json = self.vault.export_vault(data, master_pwd, use_argon2=False)
        payload = json.loads(exported_json)
        
        self.assertIn("salt", payload)
        self.assertIn("nonce", payload)
        self.assertIn("ciphertext", payload)
        self.assertEqual(payload["kdf"], "pbkdf2-sha256")

        imported_data = self.vault.import_vault(exported_json, master_pwd)
        self.assertEqual(imported_data, data, "Los datos descifrados deben coincidir con los originales")

    def test_import_wrong_password(self):
        exported_json = self.vault.export_vault("data", "correct_pwd", use_argon2=False)
        imported_data = self.vault.import_vault(exported_json, "wrong_pwd")
        self.assertIsNone(imported_data, "Debe devolver None si la contraseña es incorrecta")

class TestHIBPClient(unittest.TestCase):
    @patch('celarpass_core.hibp.requests.get')
    def test_check_password_pwned(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Simulamos que HIBP nos responde con el sufijo del hash de 'password'
        # SHA1('password') = 5BAA6 1E4C9B93F3F0682250B6CF8331B7EE68FD8
        mock_response.text = "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\n00000000000000000000000000000000000:1"
        mock_get.return_value = mock_response

        count, error = HIBPClient.check_password('password')
        self.assertEqual(count, 3861493, "Debe extraer la cantidad de veces pwned correctamente")
        self.assertEqual(error, "")