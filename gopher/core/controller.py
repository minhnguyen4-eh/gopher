"""Connection state machine. UI-agnostic: menubar and dashboard both drive this."""

import threading
import time

from . import config as cfg_module
from . import pac, proxy, tailscale
from .pac_server import PacServer
from .tunnel import SSHTunnel

OFF, CONNECTING, CONNECTED, RECONNECTING, ERROR = (
    "off", "connecting", "connected", "reconnecting", "error",
)

# state -> (dashboard level, label)
_LEVEL = {OFF: "", CONNECTING: "busy", CONNECTED: "on", RECONNECTING: "busy", ERROR: "err"}
_LABEL = {
    OFF: "off",
    CONNECTING: "connecting…",
    RECONNECTING: "reconnecting…",
    ERROR: "failed to connect",
}
RECONNECT_DELAY = 5


class NotConfigured(Exception):
    pass


class Controller:
    def __init__(self, tunnel_factory=SSHTunnel):
        self.cfg = cfg_module.load()
        self._tunnel_factory = tunnel_factory
        self._lock = threading.RLock()
        self._listeners = []
        self.state = OFF
        self.error = ""
        self._pac_server = PacServer()
        self.tunnel = self._make_tunnel()

    # -- observers -----------------------------------------------------
    def subscribe(self, callback):
        """callback(snapshot: dict) is called on every state/config change, from any thread."""
        self._listeners.append(callback)

    def _set_state(self, state: str):
        with self._lock:
            self.state = state
        self._emit()

    def _emit(self):
        snap = self.snapshot()
        for cb in self._listeners:
            cb(snap)

    def snapshot(self) -> dict:
        with self._lock:
            state = self.state
        label = _LABEL.get(state) or f"connected ({self.cfg['ssh_host']})"
        if state == ERROR and self.error:
            label = f"{label}: {self.error}"
        return {
            "state": state,
            "connected": state == CONNECTED,
            "level": _LEVEL[state],
            "status": f"Gopher Proxy: {label}",
            "config": self.cfg,
        }

    # -- actions -------------------------------------------------------
    def is_configured(self) -> bool:
        return bool(self.cfg["ssh_host"] and self.cfg["ssh_user"])

    def toggle(self):
        if self.state in (CONNECTED, CONNECTING, RECONNECTING):
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Start connecting in the background. Raises NotConfigured if host/user missing."""
        if not self.is_configured():
            raise NotConfigured("Set SSH host and user first")
        with self._lock:
            if self.state in (CONNECTED, CONNECTING):
                return
            self.state = CONNECTING
            self.error = ""
        self._emit()
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self):
        tunnel = self.tunnel
        if tailscale.is_tailnet_host(self.cfg["ssh_host"]):
            try:
                tailscale.ensure_ready()  # starts the daemon / opens the login page if needed
            except tailscale.TailscaleError as e:
                with self._lock:
                    if self.state in (CONNECTING, RECONNECTING):
                        self.error = str(e)
                        self.state = ERROR
                self._emit()
                return
        ok = tunnel.start()
        with self._lock:
            cancelled = self.state not in (CONNECTING, RECONNECTING)
        if ok and cancelled:
            tunnel.stop()
            return
        if ok:
            self._enable_pac()
            self._set_state(CONNECTED)
        elif not cancelled:
            self.error = tunnel.last_error
            self._set_state(ERROR)

    def disconnect(self):
        self.tunnel.stop()
        proxy.disable_pac()
        self._pac_server.stop()
        self._set_state(OFF)

    def shutdown(self):
        if self.state != OFF:
            self.disconnect()

    def apply_config(self, raw: dict):
        """Validate and save. Reconnects if currently up so port/domain changes take effect."""
        new = cfg_module.validate(raw, self.cfg)  # raises ValueError
        was_up = self.state in (CONNECTED, CONNECTING, RECONNECTING)
        if was_up:
            self.disconnect()
        self.cfg = new
        cfg_module.save(new)
        self.tunnel = self._make_tunnel()
        if was_up and self.is_configured():
            self.connect()
        else:
            self._emit()

    # -- internals -----------------------------------------------------
    def _enable_pac(self):
        path = pac.write(self.cfg)  # also the fallback if the PAC port is taken
        try:
            url = self._pac_server.start(
                lambda: pac.render(self.cfg["domains"], self.cfg["local_port"]))
        except OSError:
            url = f"file://{path}"
        proxy.enable_pac(url)

    def _make_tunnel(self):
        t = self._tunnel_factory(
            host=self.cfg["ssh_host"],
            user=self.cfg["ssh_user"],
            port=self.cfg["ssh_port"],
            local_port=self.cfg["local_port"],
            proxy_command=(tailscale.proxy_command()
                           if tailscale.is_tailnet_host(self.cfg["ssh_host"]) else None),
        )
        t.set_on_disconnect(self._on_tunnel_drop)
        return t

    def _on_tunnel_drop(self):
        if self.cfg.get("auto_reconnect"):
            self._set_state(RECONNECTING)
            threading.Thread(target=self._reconnect, daemon=True).start()
        else:
            proxy.disable_pac()
            self._pac_server.stop()
            self._set_state(OFF)

    def _reconnect(self):
        time.sleep(RECONNECT_DELAY)
        if self.state == RECONNECTING:
            self._connect_worker()
