#!/usr/bin/env python3
import argparse
import sys
import getpass
import json
import threading
import time
import atexit
import subprocess
import os
from celarpass_core.analyzers import analyze_password
from rich.console import Console
from rich.table import Table

from celarpass_core.generators import PasswordEngine, TOTPEngine
from celarpass_core.hibp import HIBPClient
from celarpass_core.crypto_vault import VaultExporter
import pyperclip

console = Console()

def spawn_clipboard_daemon(password_text):
    import tempfile
    import stat
    import os
    import hashlib
    
    # 1. Guardar el estado anterior del portapapeles
    old_clipboard = pyperclip.paste()
    
    # 2. Copiar la nueva contraseña al portapapeles activo
    pyperclip.copy(password_text)
    
    # 3. Calcular el hash para el daemon (Zero-Knowledge)
    target_hash = hashlib.sha256(password_text.encode('utf-8')).hexdigest()
    
    # 4. Escribir el estado ANTERIOR en un archivo temporal seguro
    fd, temp_path = tempfile.mkstemp(prefix="cpass_")
    os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, 'w') as f:
        f.write(old_clipboard if old_clipboard else "")
        
    # Lanzar daemon multiplataforma
    creationflags = 0
    start_new_session = False
    if sys.platform == "win32":
        creationflags = 0x00000008 # DETACHED_PROCESS
    else:
        start_new_session = True
        
    subprocess.Popen([sys.executable, sys.argv[0], "--bg-clipboard-server", target_hash, temp_path],
                     start_new_session=start_new_session,
                     creationflags=creationflags,
                     stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)

# Handler oculto del Daemon
if len(sys.argv) == 4 and sys.argv[1] == "--bg-clipboard-server":
    target_hash = sys.argv[2]
    temp_path = sys.argv[3]
    try:
        import os
        import hashlib
        
        # Leer el portapapeles anterior y borrar el archivo
        old_clipboard = ""
        if os.path.exists(temp_path):
            with open(temp_path, "r") as f:
                old_clipboard = f.read()
            os.remove(temp_path)
        
        # Esperar 15 segundos
        time.sleep(15)
        
        # Comprobar el portapapeles activo usando el hash
        current_text = str(pyperclip.paste())
        current_hash = hashlib.sha256(current_text.encode('utf-8')).hexdigest()
        
        if current_hash == target_hash:
            # Restaurar el estado anterior (evita el espacio en blanco)
            if old_clipboard:
                pyperclip.copy(old_clipboard)
            else:
                pyperclip.copy("")
                
    except Exception:
        pass
    finally:
        sys.exit(0)

def output_result(data_to_copy, json_dict, json_flag, copy_flag, success_msg, rich_text_lines):
    if json_flag:
        print(json.dumps(json_dict))
    else:
        if copy_flag:
            try:
                spawn_clipboard_daemon(data_to_copy)
                del data_to_copy
                console.print(f"[bold green]✔ {success_msg}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]❌ Failed to copy to clipboard (is a display server running?): {e}[/bold red]")
                for line in rich_text_lines:
                    console.print(line)
        else:
            for line in rich_text_lines:
                console.print(line)

def main():
    parser = argparse.ArgumentParser(
        description="CelarPass CLI - Advanced Cryptographic Tool\nSecurely generate passwords, tokens, check data breaches, and manage encrypted vaults.",
        epilog="""
Examples of common tasks:
  1. Generate a 20-character password, analyze it and copy to clipboard:
     celarpass-cli generate -l 20 --analyze --copy
  
  2. Generate a TOTP secret for an authenticator app:
     celarpass-cli totp -a user@example.com -i MyCompany
  
  3. Check if a password was exposed in data breaches (interactive):
     celarpass-cli hibp
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text (useful for scripting)")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # --- Comando: generate ---
    gen_parser = subparsers.add_parser(
        "generate", 
        help="Generates a secure password",
        description="Generates a cryptographically secure random password using the system's CSPRNG.",
        epilog="""
Examples:
  celarpass-cli generate                        (Default 16 chars)
  celarpass-cli generate -l 24 --no-syms -c     (24 chars, no symbols, copy)
  celarpass-cli generate --analyze              (Show entropy and crack time)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    gen_parser.add_argument("-l", "--length", type=int, default=16, help="Password length (default: 16)")
    gen_parser.add_argument("--no-upper", action="store_true", help="Exclude uppercase letters")
    gen_parser.add_argument("--no-nums", action="store_true", help="Exclude numbers")
    gen_parser.add_argument("--no-syms", action="store_true", help="Exclude symbols")
    gen_parser.add_argument("--avoid-ambiguous", action="store_true", help="Avoid ambiguous characters (I, l, 1, O, 0)")
    gen_parser.add_argument("-c", "--copy", action="store_true", help="Copy output to clipboard")
    gen_parser.add_argument("--analyze", action="store_true", help="Analyze password entropy and strength")

    # --- Comando: totp ---
    totp_parser = subparsers.add_parser(
        "totp", 
        help="Generates a TOTP secret and URI",
        description="Generates a Time-Based One-Time Password (TOTP) secret base32 key and its provisioning URI (otpauth://).",
        epilog="""
Examples:
  celarpass-cli totp -a admin@company.com -i "Prod Server"
  celarpass-cli totp -a user -i "Local VPN" --copy
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    totp_parser.add_argument("-a", "--account", required=True, help="Account name for the TOTP URI")
    totp_parser.add_argument("-i", "--issuer", required=True, help="Issuer for the TOTP URI")
    totp_parser.add_argument("-c", "--copy", action="store_true", help="Copy output to clipboard")

    # --- Comando: token ---
    token_parser = subparsers.add_parser(
        "token", 
        help="Generates a secure token for APIs or a UUID v4",
        description="Generates random URL-safe or hexadecimal tokens, Bearer strings, or UUIDs for API keys or session identifiers.",
        epilog="""
Examples:
  celarpass-cli token -m 0 -l 64     (64-byte URL-safe token)
  celarpass-cli token -m 2           (Standard UUID v4)
  celarpass-cli token -m 3 -l 32     (Bearer token)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    token_parser.add_argument("-m", "--mode", type=int, choices=[0, 1, 2, 3], default=0, help="Token type (0: URL-safe, 1: Hexadecimal, 2: UUIDv4, 3: Bearer)")
    token_parser.add_argument("-l", "--length", type=int, default=32, help="Length in bytes for modes 0, 1 and 3 (default: 32)")
    token_parser.add_argument("-c", "--copy", action="store_true", help="Copy output to clipboard")

    # --- Comando: hibp ---
    # SEGURIDAD (A-03): La contraseña se pide con getpass para evitar que
    # quede expuesta en el historial del shell o en la lista de procesos (ps aux).
    hibp_parser = subparsers.add_parser(
        "hibp", 
        help="Checks if a password has been exposed in data breaches",
        description="Checks the Have I Been Pwned API using K-Anonymity. The password is never sent in plaintext; only the first 5 characters of its SHA-1 hash are transmitted.",
        epilog="""
Examples:
  celarpass-cli hibp                     (Prompts securely without showing chars)
  echo "mypassword" | celarpass-cli hibp (Reads from stdin for scripts)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # --- Comando: vault-export ---
    # SEGURIDAD (B-03): Se elimina el flag -p/--password para evitar que la
    # contraseña maestra quede en el historial del shell o en la lista de procesos.
    # La contraseña siempre se pide de forma interactiva con getpass.
    vault_export_parser = subparsers.add_parser(
        "vault-export", 
        help="Encrypts text/JSON for the vault (AES-GCM)",
        description="Encrypts arbitrary text using AES-256-GCM. The master key is derived securely via PBKDF2 or Argon2id.",
        epilog="""
Examples:
  echo '{"secret": 123}' | celarpass-cli vault-export - --argon2 > vault.cpv
  celarpass-cli vault-export "My secret message"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    vault_export_parser.add_argument("data", help="Text to encrypt (use '-' to read from stdin)")
    vault_export_parser.add_argument("--argon2", action="store_true", help="Use Argon2id for key derivation")

    # --- Comando: vault-import ---
    # SEGURIDAD (B-03): Igual que vault-export, la contraseña siempre se pide
    # de forma interactiva para no exponerla en el historial ni en los procesos.
    vault_import_parser = subparsers.add_parser(
        "vault-import", 
        help="Decrypts an exported vault (AES-GCM)",
        description="Decrypts a vault file or string using the master password.",
        epilog="""
Examples:
  cat vault.cpv | celarpass-cli vault-import -
  celarpass-cli vault-import "eyJhbG..." 
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    vault_import_parser.add_argument("data", help="JSON of the encrypted vault (use '-' to read from stdin)")

    args = parser.parse_args()

    if args.command == "generate":
        if args.length < 8:
            console.print("[red]Error: Minimum password length is 8[/red]")
            sys.exit(1)
            
        engine = PasswordEngine()
        pwd = engine.generate_password(
            length=args.length,
            min_nums=0 if args.no_nums else 1,
            min_specs=0 if args.no_syms else 1,
            use_upper=not args.no_upper,
            use_lower=True,
            use_nums=not args.no_nums,
            use_syms=not args.no_syms,
            avoid_amb=args.avoid_ambiguous
        )
        
        output_result(
            data_to_copy=pwd,
            json_dict={"password": pwd, "length": len(pwd)},
            json_flag=args.json,
            copy_flag=args.copy,
            success_msg="Password copied to clipboard! (Will be cleared in 15 seconds)",
            rich_text_lines=[f"[bold cyan]{pwd}[/bold cyan]"]
        )
                
        if not args.json and args.analyze:
            analysis = analyze_password(pwd)
            table = Table(title="Password Analysis")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_row("Score", f"{analysis['score']} / 4")
            table.add_row("Entropy (Guesses)", f"{analysis['guesses']:,}")
            table.add_row("Crack Time", analysis.get('crack_times_display', {}).get('offline_fast_hashing_1e10_per_second', '...'))
            if analysis['feedback']['warning']:
                table.add_row("Warning", f"[red]{analysis['feedback']['warning']}[/red]")
            console.print(table)

    elif args.command == "totp":
        secret = TOTPEngine.generate_secret()
        uri = TOTPEngine.build_uri(secret, account_name=args.account, issuer=args.issuer)
        output_result(
            data_to_copy=uri,
            json_dict={"totp_secret": secret, "totp_uri": uri},
            json_flag=args.json,
            copy_flag=args.copy,
            success_msg="TOTP URI copied to clipboard! (Will be cleared in 15 seconds)",
            rich_text_lines=[f"Secret: [bold cyan]{secret}[/bold cyan]", f"URI: [bold cyan]{uri}[/bold cyan]"]
        )

    elif args.command == "token":
        if args.mode == 2 and args.length != 32:
            console.print("[yellow]Warning: Custom length is ignored for UUIDv4 (mode 2)[/yellow]")
        elif args.length < 8 and args.mode != 2:
            console.print("[red]Error: Minimum token length is 8[/red]")
            sys.exit(1)
            
        engine = PasswordEngine()
        token = engine.generate_api_token(mode=args.mode, length=args.length)
        output_result(
            data_to_copy=token,
            json_dict={"token": token, "mode": args.mode},
            json_flag=args.json,
            copy_flag=args.copy,
            success_msg="Token copied to clipboard! (Will be cleared in 15 seconds)",
            rich_text_lines=[f"[bold cyan]{token}[/bold cyan]"]
        )

    elif args.command == "hibp":
        if not sys.stdin.isatty():
            password = sys.stdin.read(256).strip()
        else:
            password = getpass.getpass("🔑 Password to check (hidden): ")
            
        try:
            count, error = HIBPClient.check_password(password)
        except Exception as e:
            count, error = -1, str(e)
        del password
        
        if args.json:
            print(json.dumps({"exposed": count > 0, "count": count, "error": error}))
        else:
            if error:
                console.print(f"[bold yellow]❌ Error: {error}[/bold yellow]")
            elif count > 0:
                console.print(f"[bold red]⚠ Exposed {count} times[/bold red]")
            else:
                console.print(f"[bold green]✔ Safe (0 times)[/bold green]")
        
    elif args.command == "vault-export":
        if args.data == '-':
            if sys.stdin.isatty():
                console.print("[yellow]Waiting for input from stdin... (Press Ctrl+D to finish or Ctrl+C to cancel)[/yellow]")
            data = sys.stdin.read()
        else:
            data = args.data
            
        password = getpass.getpass("🔑 Master password: ")
        exporter = VaultExporter()
        try:
            result = exporter.export_vault(data, password, args.argon2)
            if args.json:
                print(json.dumps({"vault": result}))
            else:
                console.print(f"[bold cyan]{result}[/bold cyan]")
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]❌ Export Error: {e}[/bold red]")
            sys.exit(1)
        finally:
            del password
        
    elif args.command == "vault-import":
        if args.data == '-':
            if sys.stdin.isatty():
                console.print("[yellow]Waiting for input from stdin... (Press Ctrl+D to finish or Ctrl+C to cancel)[/yellow]")
            data = sys.stdin.read()
        else:
            data = args.data
            
        password = getpass.getpass("🔑 Master password: ")
        exporter = VaultExporter()
        try:
            result = exporter.import_vault(data, password)
            if result:
                if args.json:
                    print(json.dumps({"data": result}))
                else:
                    console.print(result)
            else:
                if args.json:
                    print(json.dumps({"error": "Incorrect password or corrupted data"}))
                else:
                    console.print("[bold red]❌ Error: Incorrect password or corrupted data.[/bold red]")
                sys.exit(1)
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]❌ Import Error: {e}[/bold red]")
            sys.exit(1)
        finally:
            del password
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()