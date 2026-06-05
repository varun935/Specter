# Specter

A terminal-based post-exploitation framework for Linux. Provides a reverse shell, file transfer, persistence, and system reconnaissance over an encrypted C2 channel.

Built for educational purposes and authorized penetration testing only.

---

## Disclaimer

Do not use Specter on systems or networks you do not own or have explicit permission to test. The author is not responsible for any misuse or damage.

---

## Features

- [✅] Reverse shell with multi-client management
- [✅] TLS 1.3 encrypted C2 traffic
- [✅] Chunked file upload and download
- [✅] Persistence (crontab, bashrc, systemd)
- [✅] Modular plugin system
- [ ] Remote access via Ngrok / DDNS
- [ ] Screenshot / keystroke logging
- [ ] Terminal UI

---

## Setup

**1. Install dependencies (once)**
```bash
pip install cryptography
```

**2. Generate TLS certificate (once)**
```bash
python attacker/setup.py
```
Generates `attacker/cert.pem` and `attacker/key.pem`. The certificate is automatically embedded into `target/shell.py`. The private key stays on your machine.

**3. Set attacker IP in `target/shell.py`**
```python
target_ip = "192.168.x.x"
```

**4. Copy agent to target**
```bash
scp target/shell.py user@target:/path/to/shell.py
```

**5. Start C2 server**
```bash
python attacker/c2.py
```

**6. Run agent on target**
```bash
python shell.py
```
The agent retries every 10 seconds until the C2 is reachable.

---

## Commands

### Main menu

| Command | Description |
|---|---|
| `list` | List connected clients |
| `select <index>` | Open a shell for a client |
| `exit` | Shut down the C2 server |

### Client shell

| Command | Description |
|---|---|
| `help` | Show commands and loaded plugins |
| `back` | Return to main menu |
| `exit` | Terminate the agent on the target |
| `download <remote_path>` | Download a file to `attacker/downloads/` |
| `upload <local_path> <remote_path>` | Upload a file to the target |
| Any shell command | Executed on the target |

---

## Encryption

All traffic is encrypted with TLS 1.3 using AES-256-GCM. `setup.py` generates a self-signed certificate pair:

| File | Purpose | Location |
|---|---|---|
| `cert.pem` | Public certificate | Attacker machine + embedded in `shell.py` |
| `key.pem` | Private key | Attacker machine only |

On each connection the agent verifies the server certificate against the embedded copy. Any connection without the matching private key is rejected. A fresh session key is negotiated per connection via Diffie-Hellman — past sessions cannot be decrypted even if `key.pem` is later compromised.

To rotate the certificate:
```bash
python attacker/setup.py
scp target/shell.py user@target:/path/to/shell.py
```

---

## Plugins

Plugins in `attacker/plugins/` are loaded automatically on startup.

### `recon_basic`
Runs `whoami && hostname && uname -a && ip a && w` on the target.
```
SPECTER:...> recon_basic
```

### `persistence`
Installs or removes persistence on the target.
```
SPECTER:...> persistence
```

| Option | Method | Trigger |
|---|---|---|
| 1 | Crontab | `@reboot` |
| 2 | Bashrc | New login shell |
| 3 | Systemd user service | Boot, auto-restarts |
| 4 | Remove crontab | — |
| 5 | Remove bashrc | — |
| 6 | Remove systemd | — |

---

## License

MIT — see `LICENSE`.
