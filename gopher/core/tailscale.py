"""Userspace Tailscale, for Macs where the Tailscale app / network extension is blocked.

Runs `tailscaled --tun=userspace-networking` as a plain process (no root, no VPN
extension). There is no tailscale interface, so traffic to 100.x hosts must go through
the local SOCKS5 port; SSH does that with a ProxyCommand.
"""

import functools
import ipaddress
import json
import os
import re
import subprocess
import time
import webbrowser

TS_DIR = os.path.expanduser("~/.tailscale")
SOCKET = os.path.join(TS_DIR, "tailscaled.sock")
SOCKS_PORT = 1055
DAEMON_WAIT = 10
LOGIN_TIMEOUT = 120

_SEARCH_PATH = os.pathsep.join(["/opt/homebrew/bin", os.environ.get("PATH", ""), "/usr/local/bin"])
_URL_RE = re.compile(r"https://\S+")
_TAILNET = ipaddress.ip_network("100.64.0.0/10")


class TailscaleError(Exception):
    pass


def is_tailnet_host(host: str) -> bool:
    if host.endswith(".ts.net"):
        return True
    try:
        return ipaddress.ip_address(host) in _TAILNET
    except ValueError:
        return False


def proxy_command() -> str:
    return f"nc -X 5 -x 127.0.0.1:{SOCKS_PORT} %h %p"


def _works(path: str) -> bool:
    # skips stale wrappers, e.g. /usr/local/bin/tailscale left behind by the removed app
    try:
        return subprocess.run([path, "--version"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@functools.cache
def _bin(name: str) -> str:
    for directory in _SEARCH_PATH.split(os.pathsep):
        path = os.path.join(directory, name)
        if os.access(path, os.X_OK) and _works(path):
            return path
    raise TailscaleError(f"{name} not found (brew install tailscale)")


def _cli(*args, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_bin("tailscale"), "--socket", SOCKET, *args],
        capture_output=True, text=True, **kw,
    )


def backend_state() -> str | None:
    """Tailscale BackendState ("Running", "NeedsLogin", ...), or None if the daemon is down."""
    try:
        return json.loads(_cli("status", "--json", timeout=5).stdout).get("BackendState")
    except (subprocess.TimeoutExpired, ValueError):
        return None


def _start_daemon():
    os.makedirs(TS_DIR, exist_ok=True)
    with open(os.path.join(TS_DIR, "tailscaled.out"), "ab") as log:
        subprocess.Popen(
            [
                _bin("tailscaled"),
                "--tun=userspace-networking",
                f"--socks5-server=localhost:{SOCKS_PORT}",
                f"--socket={SOCKET}",
                f"--statedir={TS_DIR}",
            ],
            stdout=log, stderr=log, start_new_session=True,  # outlives Gopher; state is persisted
        )


def ensure_ready():
    """Start the daemon if needed and log in (opening the browser) until Running."""
    state = backend_state()
    if state is None:
        _start_daemon()
        deadline = time.monotonic() + DAEMON_WAIT
        while state is None and time.monotonic() < deadline:
            time.sleep(0.5)
            state = backend_state()
        if state is None:
            raise TailscaleError("tailscaled did not start")
    if state == "Running":
        return

    opened = False
    proc = subprocess.Popen(
        [_bin("tailscale"), "--socket", SOCKET, "up", f"--timeout={LOGIN_TIMEOUT}s"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in proc.stdout:
        match = _URL_RE.search(line)
        if match and not opened:
            opened = True
            webbrowser.open(match.group())
    proc.wait()
    if backend_state() != "Running":
        raise TailscaleError("Tailscale login not completed")
