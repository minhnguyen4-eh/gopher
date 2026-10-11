# Gopher 🐹

Route Discord traffic through an SSH SOCKS5 tunnel — a macOS menubar app.

## The big picture

The office network blocks Discord. Gopher sends **only Discord traffic** out through another computer (your home PC) that is not blocked. Everything else on your Mac is untouched.

```
Discord ──▶ macOS proxy settings (PAC) ──▶ SOCKS5 port on your Mac ──▶ SSH tunnel ──▶ home PC ──▶ Discord servers
            "is this a Discord site?"       127.0.0.1:1080             encrypted      (not blocked)
```

### What is SOCKS5?

SOCKS5 is a simple, general-purpose **proxy protocol**. An app that speaks SOCKS5 does not connect to a website directly. It connects to the proxy and says "please connect me to discord.com:443". The proxy makes the connection and passes the data back and forth. The website sees the proxy's address, not yours.

It works for any kind of TCP traffic (web pages, WebSocket, API calls), not just web pages. It does **not** carry UDP in this setup, which is why Discord voice and video do not work.

### The four pieces

| Piece | What it does | Analogy |
|-------|--------------|---------|
| **PAC file** | A tiny script that macOS asks for every URL: "direct, or through the proxy?". It answers "proxy" for the configured domains (`discord.com`, ...) and "direct" for everything else. | A receptionist deciding which calls to forward |
| **SOCKS5 proxy on your Mac** | `ssh -N -D 1080` opens port `1080` on your Mac and speaks SOCKS5 there. Whatever arrives is sent into the SSH tunnel. | The mailbox you drop letters in |
| **SSH tunnel** | An encrypted connection from your Mac to the home PC. The office network only sees SSH traffic, not Discord. | A sealed pipe under the office wall |
| **Tailscale** | A private network between your devices, so your Mac can reach the home PC (`100.x.x.x`) even behind NAT or a firewall, with no router setup. | A private phone line between your devices |

### What happens when you click Connect

1. Gopher starts Tailscale (if the host is a Tailscale address) so the home PC is reachable.
2. Gopher opens the SSH tunnel, which creates the SOCKS5 port `127.0.0.1:1080` on your Mac.
3. Gopher serves the PAC file locally and tells macOS to use it.
4. You open Discord. macOS asks the PAC file about `discord.com`. The answer is "use SOCKS5 at 127.0.0.1:1080".
5. Discord's traffic goes into the SSH tunnel, comes out at the home PC, and reaches Discord from there.
6. Any other site (for example, `google.com`) gets "DIRECT" and goes out normally.

Click Disconnect and Gopher turns the proxy setting off and closes the tunnel, so your Mac goes back to normal.

## Setup

```bash
pip install -e ".[dev]"
```

## Run

```bash
python -m gopher
```

On first run: menubar → "Open Dashboard" → enter your SSH host and user.

## Test

```bash
pytest
```

## Build the .app

```bash
pyinstaller --windowed --name Gopher --paths . --add-data "gopher/ui/dashboard/index.html:gopher/ui/dashboard" gopher/__main__.py
```

## Project structure

```
gopher/
├── pyproject.toml
├── gopher/
│   ├── __main__.py          # entry point
│   ├── core/                # no UI dependencies
│   │   ├── config.py        # ~/.config/gopher/config.json + validation
│   │   ├── tunnel.py        # SSH tunnel process
│   │   ├── proxy.py         # macOS networksetup PAC control
│   │   ├── pac.py           # PAC file generated from config
│   │   ├── pac_server.py    # serves the PAC over http://127.0.0.1 (apps ignore file:// PACs)
│   │   ├── tailscale.py     # userspace Tailscale daemon + login, for tailnet SSH hosts
│   │   └── controller.py    # connect/disconnect/reconnect state machine
│   └── ui/
│       ├── menubar.py       # rumps menubar
│       └── dashboard/       # local web UI (server.py + index.html)
├── tests/
└── GUIDANCE.md              # step-by-step setup: Tailscale + Windows SSH host
```

For a full setup walkthrough (Tailscale, Windows OpenSSH, SSH keys), see [GUIDANCE.md](GUIDANCE.md).

## How it works (technical details)

1. If the SSH host is a Tailscale address (`100.x.x.x` or `*.ts.net`), starts a userspace `tailscaled` (no app, no root) and logs in through the browser if needed
2. Opens an SSH tunnel: `ssh -N -D 1080 user@host` (through a ProxyCommand for Tailscale hosts). A leftover tunnel from a crashed Gopher is stopped first
3. Serves a PAC file from `http://127.0.0.1:18080/proxy.pac`, generated from the configured domains and local port. If that port is taken, falls back to `~/.config/gopher/gopher.pac`
4. Points the macOS system PAC proxy at that URL
5. The PAC file routes the configured domains to `SOCKS5 127.0.0.1:<local_port>`
6. All other traffic goes DIRECT and is unaffected

Voice/video (UDP) does not go through the SSH SOCKS tunnel. Failures (SSH error, Tailscale login not finished) are shown in the menubar status.

## Config

Stored at `~/.config/gopher/config.json`:

```json
{
  "ssh_host": "your.server.com",
  "ssh_user": "username",
  "ssh_port": 22,
  "local_port": 1080,
  "auto_reconnect": true,
  "domains": ["discord.com", "discordapp.com"]
}
```

## Requirements

- Python 3.11+
- macOS 12+
- An SSH key set up on the remote server (no password prompt)
- `brew install tailscale` only if the server is reached over Tailscale
