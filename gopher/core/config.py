import json
import os
import re

CONFIG_DIR = os.path.expanduser("~/.config/gopher")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT = {
    "ssh_host": "",
    "ssh_user": "",
    "ssh_port": 22,
    "local_port": 1080,
    "auto_reconnect": True,
    "domains": [
        "discord.com",
        "discordapp.com",
        "discord.gg",
        "discordapp.net",
        "discord.media",
        "discordcdn.com",
    ],
}

_DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+$")


def load() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT.copy()
    with open(CONFIG_PATH) as f:
        return {**DEFAULT, **json.load(f)}


def save(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def validate(raw: dict, base: dict) -> dict:
    """Return a new config built from `base` + user-supplied `raw`; raise ValueError if invalid."""
    cfg = dict(base)
    for key in ("ssh_host", "ssh_user"):
        if key in raw:
            cfg[key] = str(raw[key]).strip()
    for key in ("ssh_port", "local_port"):
        if key in raw:
            port = int(raw[key])
            if not 1 <= port <= 65535:
                raise ValueError(f"{key} out of range")
            cfg[key] = port
    if "auto_reconnect" in raw:
        cfg["auto_reconnect"] = bool(raw["auto_reconnect"])
    if "domains" in raw:
        domains = [d.strip().lower().lstrip("*.") for d in raw["domains"] if d.strip()]
        bad = [d for d in domains if not _DOMAIN_RE.match(d)]
        if bad:
            raise ValueError(f"invalid domain: {bad[0]}")
        cfg["domains"] = sorted(set(domains))
    return cfg
