"""macOS menubar (rumps). Thin layer over core.Controller."""

import rumps

from ..core.controller import (
    CONNECTED, CONNECTING, ERROR, RECONNECTING, Controller, NotConfigured,
)
from .dashboard.server import Dashboard

ICONS = {CONNECTED: "🐹", ERROR: "💀"}
DEFAULT_ICON = "🐭"
DOTS = {CONNECTED: "🟢", CONNECTING: "🟡", RECONNECTING: "🟡", ERROR: "🔴"}
DEFAULT_DOT = "⚪"


class MenubarApp(rumps.App):
    def __init__(self, controller: Controller):
        super().__init__("Gopher", title=DEFAULT_ICON, quit_button=None)
        self.controller = controller
        self.dashboard = Dashboard(controller)

        self.status_item = rumps.MenuItem("", callback=None)
        self.toggle_item = rumps.MenuItem("Connect", callback=self.on_toggle)
        self.menu = [
            self.status_item,
            None,
            self.toggle_item,
            rumps.MenuItem("Open Dashboard", callback=self.on_open_dashboard),
            None,
            rumps.MenuItem("Quit Gopher", callback=self.on_quit),
        ]

        controller.subscribe(self.render)
        self.render(controller.snapshot())

    def render(self, snap: dict):
        state = snap["state"]
        self.title = ICONS.get(state, DEFAULT_ICON)
        self.status_item.title = f"{DOTS.get(state, DEFAULT_DOT)} {snap['status']}"
        busy = state in (CONNECTING, RECONNECTING)
        self.toggle_item.title = (
            "Connecting…" if busy
            else "Disconnect" if snap["connected"]
            else "Retry" if state == ERROR
            else "Connect"
        )
        self.toggle_item.set_callback(None if state == CONNECTING else self.on_toggle)

    def on_toggle(self, _):
        try:
            self.controller.toggle()
        except NotConfigured as e:
            rumps.notification("Gopher", str(e), "Opening dashboard…")
            self.dashboard.open()

    def on_open_dashboard(self, _):
        self.dashboard.open()

    def on_quit(self, _):
        self.controller.shutdown()
        self.dashboard.close()
        rumps.quit_application()
