# Gopher 🐹

Route Discord traffic through an SSH SOCKS5 tunnel — a macOS menubar app.

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
│   │   └── controller.py    # connect/disconnect/reconnect state machine
│   └── ui/
│       ├── menubar.py       # rumps menubar
│       └── dashboard/       # local web UI (server.py + index.html)
└── tests/
```

## How it works

1. Opens an SSH tunnel: `ssh -N -D 1080 user@host`
2. Generates a PAC file at `~/.config/gopher/gopher.pac` from the configured domains and local port
3. Points the macOS system PAC proxy at that file
4. The PAC file routes the configured domains to `SOCKS5 127.0.0.1:<local_port>`
5. All other traffic goes DIRECT and is unaffected

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
