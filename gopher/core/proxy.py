"""macOS system PAC proxy control via `networksetup`."""

import subprocess


def _get_network_service() -> str:
    """Return active network service name (Wi-Fi or Ethernet)."""
    result = subprocess.run(
        ["networksetup", "-listnetworkserviceorder"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        for name in ("Wi-Fi", "Ethernet", "USB 10/100/1000 LAN"):
            if name in line and "(*)" not in line:
                return name
    return "Wi-Fi"


def enable_pac(pac_url: str, service: str | None = None) -> bool:
    svc = service or _get_network_service()
    result = subprocess.run(
        ["networksetup", "-setautoproxyurl", svc, pac_url],
        capture_output=True,
    )
    subprocess.run(["networksetup", "-setautoproxystate", svc, "on"], capture_output=True)
    return result.returncode == 0


def disable_pac(service: str | None = None) -> bool:
    svc = service or _get_network_service()
    result = subprocess.run(
        ["networksetup", "-setautoproxystate", svc, "off"],
        capture_output=True,
    )
    return result.returncode == 0

