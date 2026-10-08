"""Generate the PAC file from config, so domains and port are never hardcoded."""

import json
import os

from .config import CONFIG_DIR

PAC_PATH = os.path.join(CONFIG_DIR, "gopher.pac")

_TEMPLATE = """function FindProxyForURL(url, host) {{
    var domains = {domains};
    host = host.toLowerCase();
    for (var i = 0; i < domains.length; i++) {{
        if (host === domains[i] || dnsDomainIs(host, "." + domains[i])) {{
            return "SOCKS5 127.0.0.1:{port}; SOCKS 127.0.0.1:{port}";
        }}
    }}
    return "DIRECT";
}}
"""


def render(domains: list[str], port: int) -> str:
    return _TEMPLATE.format(domains=json.dumps(domains), port=int(port))


def write(cfg: dict, path: str | None = None) -> str:
    path = path or PAC_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(render(cfg["domains"], cfg["local_port"]))
    return path
