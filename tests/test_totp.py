import unittest
import urllib.parse
from celarpass_core.generators import TOTPEngine

class TestTOTPEngine(unittest.TestCase):
    def test_basic_uri(self):
        uri = TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", "test@example.com", "ExampleCo")
        self.assertEqual(
            uri,
            "otpauth://totp/ExampleCo:test%40example.com?secret=JBSWY3DPEHPK3PXP&algorithm=SHA1&digits=6&period=30&issuer=ExampleCo"
        )
        
    def test_special_chars_encoding(self):
        uri = TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", "user:name & more", "My Cool App: Pro")
        self.assertTrue("My%20Cool%20App%3A%20Pro:user%3Aname%20%26%20more" in uri)
        self.assertTrue("issuer=My+Cool+App%3A+Pro" in uri)

    def test_no_issuer(self):
        uri = TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", "test@example.com", "")
        self.assertTrue("otpauth://totp/test%40example.com?" in uri)
        self.assertFalse("issuer=" in uri)

    def test_invalid_secret(self):
        with self.assertRaisesRegex(ValueError, "Base32 válida"):
            TOTPEngine.build_uri("123INVALID!!!", "test@example.com")
            
    def test_empty_account(self):
        with self.assertRaisesRegex(ValueError, "no puede consistir solo de espacios"):
            TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", "   ")
            
    def test_max_length(self):
        long_str = "a" * 101
        with self.assertRaisesRegex(ValueError, "excede la longitud máxima"):
            TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", long_str)
            
    def test_control_chars(self):
        with self.assertRaisesRegex(ValueError, "caracteres de control no permitidos"):
            TOTPEngine.build_uri("JBSWY3DPEHPK3PXP", "test\nuser")

    def test_round_trip(self):
        # Generate URI
        original_secret = "JBSWY3DPEHPK3PXP"
        original_account = "user@example.com"
        original_issuer = "Acme Corp"
        
        uri = TOTPEngine.build_uri(original_secret, original_account, original_issuer)
        
        # Parse it back
        parsed = urllib.parse.urlparse(uri)
        self.assertEqual(parsed.scheme, "otpauth")
        self.assertEqual(parsed.netloc, "totp")
        
        # Path should be /Acme%20Corp:user%40example.com
        path = parsed.path.lstrip('/')
        issuer_label, account_label = path.split(':')
        self.assertEqual(urllib.parse.unquote(issuer_label), original_issuer)
        self.assertEqual(urllib.parse.unquote(account_label), original_account)
        
        # Query params
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(query['secret'][0], original_secret)
        self.assertEqual(query['issuer'][0], original_issuer)
        self.assertEqual(query['algorithm'][0], "SHA1")
        self.assertEqual(int(query['digits'][0]), 6)
        self.assertEqual(int(query['period'][0]), 30)

if __name__ == '__main__':
    unittest.main()
