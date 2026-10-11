# Gopher — Project Plan

A macOS menubar app that routes Discord traffic through a SOCKS5 proxy, bypassing a corporate Cloudflare filter.

---

## Problem

The corporate network goes through Cloudflare Gateway, which blocks Discord. We need to route only Discord traffic around the filter without affecting anything else.

---

## How it works

```
Discord app → macOS PAC proxy → SOCKS5 proxy (external) → Discord servers
                                      ↑
                            SSH tunnel or direct
```

1. **PAC file** (generated from config) — sends only the configured domains (`discord.com`, `discordapp.com`, ...) through SOCKS5; everything else is DIRECT. Served at `http://127.0.0.1:18080/proxy.pac` because apps ignore `file://` PAC URLs (file fallback if the port is busy)
2. **SOCKS5 proxy** — an SSH tunnel (`ssh -N -D 1080`) or a hosted proxy server
3. **macOS system proxy** — set via `networksetup -setautoproxyurl`
4. **Tailscale (userspace)** — for tailnet hosts, `tailscaled --tun=userspace-networking` runs as a normal process and SSH reaches the host through its SOCKS5 port (`nc -X 5 -x localhost:1055`)
5. **Menubar app** — toggle on/off, open the dashboard, auto-reconnect

---

## Stack

- **Language**: Python 3.11+
- **Menubar**: [rumps](https://github.com/jaredks/rumps) — native macOS menubar
- **Dashboard**: local web UI served on `127.0.0.1` (standard library `http.server`)
- **Build**: PyInstaller → `.app` bundle

---

## Project structure

```
gopher/
├── pyproject.toml
├── gopher/
│   ├── __main__.py          # entry point
│   ├── core/                # no UI dependencies
│   │   ├── config.py        # load/save/validate ~/.config/gopher/config.json
│   │   ├── tunnel.py        # SSH tunnel manager — start/stop/monitor process
│   │   ├── proxy.py         # macOS networksetup PAC control
│   │   ├── pac.py           # PAC file generated from config
│   │   ├── pac_server.py    # serves the PAC over http://127.0.0.1 (apps ignore file:// PACs)
│   │   ├── tailscale.py     # userspace Tailscale daemon + login, for tailnet SSH hosts
│   │   └── controller.py    # connect/disconnect/reconnect state machine
│   └── ui/
│       ├── menubar.py       # rumps menubar, thin layer over the controller
│       └── dashboard/       # local web UI (server.py + index.html)
├── tests/
├── GUIDANCE.md
├── PLAN.md
└── README.md
```

`core/` never imports `ui/`. Both the menubar and the dashboard drive the same `Controller`.

---

## Proxy backend options

### Option A: SSH tunnel (current)

Needs a remote server you can SSH into. The app opens the tunnel on connect.

```bash
ssh -N -D 1080 user@your-server
```

The PAC file points at `127.0.0.1:<local_port>`.

**Pros**: Encrypted end to end, no public port exposed  
**Cons**: Needs a server with SSH access

---

### Option B: Fly.io hosted SOCKS5 (simpler)

Deploy `microsocks` on the Fly.io free tier. The app connects directly, so `tunnel.py` is not needed.

```toml
# fly.toml
app = "gopher-proxy"

[[services]]
  internal_port = 1080
  protocol = "tcp"
  [[services.ports]]
    port = 1080
```

```dockerfile
FROM alpine
RUN apk add --no-cache microsocks
CMD ["microsocks", "-p", "1080"]
```

The PAC file would point at `socks5://gopher-proxy.fly.dev:1080`.

**Pros**: Deploys in minutes, no server to manage, free  
**Cons**: Traffic passes through Fly.io infrastructure (generally trustworthy), no extra encryption

---

### Option C: Oracle Cloud Free Tier

Two ARM VMs, free permanently, with a real static IP. Set up like any VPS and use the SSH tunnel (Option A).

**Pros**: Free forever, static IP, full control  
**Cons**: Slightly more setup

---

### Option D: Tailscale + a home machine (current setup)

Install Tailscale on a home machine (Windows, with OpenSSH Server) and run the userspace CLI on the Mac, then SSH over the Tailscale IP (`100.x.x.x`). Gopher starts and logs in to Tailscale itself. See [GUIDANCE.md](GUIDANCE.md).

**Pros**: No cloud needed, peer-to-peer, free  
**Cons**: The home machine must stay on

---

## Comparison

| Option | Cost | Setup time | Reliable | Recommended |
|--------|------|------------|----------|-------------|
| SSH + VPS | ~$5/month | 20 min | ✅ | If you want stability |
| Fly.io SOCKS5 | Free | 10 min | ✅ | **Quick win** |
| Oracle Cloud | Free | 30 min | ✅ | If you want a real free VPS |
| Tailscale | Free | 10 min | Depends on the home machine | If you have a home machine |

---

## Timeline

| Day | Work |
|-----|------|
| 1 | Core app (tunnel + PAC + proxy) — done ✅ |
| 2 | Menubar status UI, dashboard, core/ui refactor — done ✅ |
| 3 | Tailscale userspace support, PAC over http, clearer errors, cleanup — done ✅ |
| 4 | Build `.app`, launch at login, distribute |

---

## Possible improvements

- [ ] Multiple profiles (several servers)
- [ ] Bandwidth indicator
- [ ] Auto-start at login (LaunchAgent)
- [ ] Notch widget (macOS 14+)
- [x] Configurable domain list (Spotify, Telegram, ...)
- [ ] Automatic updater

---

## Requirements

- macOS 12+
- Python 3.11+
- An SSH key set up on the remote server (if using the SSH tunnel)
- A remote server / Fly.io account (if using a hosted proxy)
