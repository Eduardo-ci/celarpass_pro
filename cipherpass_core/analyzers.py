import math
from typing import Tuple
from zxcvbn import zxcvbn

MIN_UNIQUE_RATIO: float = 0.30

def QT_TRANSLATE_NOOP(context, text):
    return text

def analyze_password(password: str, charset: int = None) -> dict:
    """
    Llama a zxcvbn y corrige el falso negativo para contraseñas aleatorias
    sobre-estimando los intentos (guesses) basándose en la entropía matemática.
    """
    results = zxcvbn(password)
    
    sequence = results.get("sequence", [])
    if len(sequence) == 1 and sequence[0].get("pattern") == "bruteforce":
        if charset is None:
            has_lower = any(c.islower() for c in password)
            has_upper = any(c.isupper() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_symbol = any(not c.isalnum() for c in password)
            
            cardinality = 0
            if has_lower: cardinality += 26
            if has_upper: cardinality += 26
            if has_digit: cardinality += 10
            if has_symbol: cardinality += 33 # Símbolos comunes
        else:
            cardinality = charset

        if cardinality > 0:
            math_guesses = cardinality ** len(password)
            if math_guesses > results.get('guesses', 0):
                results['guesses'] = math_guesses
                results['guesses_log10'] = math.log10(math_guesses)
                
                # Recalcular todos los tiempos
                crack_times = results.setdefault('crack_times_seconds', {})
                crack_times['offline_fast_hashing_1e10_per_second'] = float(math_guesses / 1e10)
                crack_times['offline_slow_hashing_1e4_per_second'] = float(math_guesses / 1e4)
                crack_times['online_no_throttling_10_per_second'] = float(math_guesses / 10.0)
                crack_times['online_throttling_100_per_hour'] = float(math_guesses / (100.0 / 3600.0))
                
                def display_time(seconds):
                    minute, hour, day, month, year, century = 60, 3600, 86400, 2678400, 31536000, 3153600000
                    if seconds < 1: return "less than a second"
                    if seconds < minute: return f"{round(seconds)} seconds"
                    if seconds < hour: return f"{round(seconds / minute)} minutes"
                    if seconds < day: return f"{round(seconds / hour)} hours"
                    if seconds < month: return f"{round(seconds / day)} days"
                    if seconds < year: return f"{round(seconds / month)} months"
                    if seconds < century: return f"{round(seconds / year)} years"
                    return "centuries"
                
                display_dict = results.setdefault('crack_times_display', {})
                for k, v in crack_times.items():
                    display_dict[k] = display_time(v)
                    
    return results

class StrengthAnalyzer:
    """Analiza la fortaleza de contraseñas basándose en zxcvbn y entropía matemática."""
    
    @staticmethod
    def get_unified_metrics(password: str) -> Tuple[int, str, str, float, str]:
        if not password:
            return 0, "", "...", 0.0, ""

        results = analyze_password(password)
        crack_seconds = float(results["crack_times_seconds"]["offline_slow_hashing_1e4_per_second"])
        warning = results["feedback"]["warning"]

        if len(password) > 6:
            unique_chars = len(set(password))
            if (unique_chars / len(password)) < MIN_UNIQUE_RATIO:
                crack_seconds = min(crack_seconds, 60.0)
                warning = QT_TRANSLATE_NOOP("CipherPassApp", "Muchos caracteres repetidos")

        if crack_seconds < 86400:
            val, color, msg = 15, "#e74c3c", QT_TRANSLATE_NOOP("CipherPassApp", "Muy Débil")
        elif crack_seconds < 31536000:
            val, color, msg = 35, "#e67e22", QT_TRANSLATE_NOOP("CipherPassApp", "Débil")
        elif crack_seconds < 315360000:
            val, color, msg = 55, "#f1c40f", QT_TRANSLATE_NOOP("CipherPassApp", "Regular")
        elif crack_seconds < 3153600000:
            val, color, msg = 80, "#2ecc71", QT_TRANSLATE_NOOP("CipherPassApp", "Buena")
        else:
            val, color, msg = 100, "#3498db", QT_TRANSLATE_NOOP("CipherPassApp", "Muy Fuerte")

        return val, color, msg, crack_seconds, warning

    @staticmethod
    def calculate_entropy_preview(length: int, use_upper: bool, use_lower: bool, use_nums: bool, use_syms: bool) -> Tuple[int, str, str]:
        pool_size = 0
        if use_upper: pool_size += 26
        if use_lower: pool_size += 26
        if use_nums: pool_size += 10
        if use_syms: pool_size += 30

        if pool_size == 0 or length == 0:
            return 0, "#e74c3c", QT_TRANSLATE_NOOP("CipherPassApp", "Débil")

        entropy = length * math.log2(pool_size)
        val = min(95, int((entropy / 80.0) * 100))
        
        if entropy < 50:
            color, msg = "#e74c3c", QT_TRANSLATE_NOOP("CipherPassApp", "Débil")
        elif entropy < 75:
            color, msg = "#f39c12", QT_TRANSLATE_NOOP("CipherPassApp", "Moderada")
        else:
            color, msg = "#2ecc71", QT_TRANSLATE_NOOP("CipherPassApp", "Fuerte")

        return val, color, msg