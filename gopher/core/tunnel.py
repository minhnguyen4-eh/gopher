import os
import signal
import subprocess
import threading
import time


class SSHTunnel:
    def __init__(self, host: str, user: str, port: int = 22, local_port: int = 1080):
        self.host = host
        self.user = user
        self.port = port
        self.local_port = local_port
        self._process: subprocess.Popen | None = None
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._on_disconnect = None

    def set_on_disconnect(self, callback):
        self._on_disconnect = callback

    def start(self) -> bool:
        if self._process and self._process.poll() is None:
            return True
        cmd = [
            "ssh",
            "-N",
            "-D", str(self.local_port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-p", str(self.port),
            f"{self.user}@{self.host}",
        ]
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            # Give it a moment to establish
            time.sleep(1.5)
            if self._process.poll() is not None:
                return False
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
            self._monitor_thread.start()
            return True
        except Exception:
            return False

    def stop(self):
        self._running = False
        if self._process and self._process.poll() is None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except Exception:
                self._process.terminate()
        self._process = None

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _monitor(self):
        while self._running and self._process:
            if self._process.poll() is not None:
                self._running = False
                if self._on_disconnect:
                    self._on_disconnect()
                break
            time.sleep(3)
