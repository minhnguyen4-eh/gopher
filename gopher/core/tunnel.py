import os
import signal
import subprocess
import threading
import time


def reap_stale_tunnel(local_port: int):
    """Stop a leftover `ssh -N -D <port>` (ours, orphaned by a crashed/killed Gopher) holding the port."""
    out = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{local_port}", "-sTCP:LISTEN", "-t"],
        capture_output=True, text=True,
    ).stdout
    for pid in set(out.split()):
        cmd = subprocess.run(
            ["ps", "-o", "command=", "-p", pid], capture_output=True, text=True,
        ).stdout.strip()
        if cmd.startswith(f"ssh -N -D {local_port} "):
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                continue
            time.sleep(0.5)


class SSHTunnel:
    def __init__(self, host: str, user: str, port: int = 22, local_port: int = 1080,
                 proxy_command: str | None = None):
        self.host = host
        self.user = user
        self.port = port
        self.local_port = local_port
        self.proxy_command = proxy_command
        self.last_error = ""
        self._process: subprocess.Popen | None = None
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._on_disconnect = None

    def set_on_disconnect(self, callback):
        self._on_disconnect = callback

    def start(self) -> bool:
        if self._process and self._process.poll() is None:
            return True
        reap_stale_tunnel(self.local_port)
        cmd = [
            "ssh",
            "-N",
            "-D", str(self.local_port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-p", str(self.port),
        ]
        if self.proxy_command:
            cmd += ["-o", f"ProxyCommand={self.proxy_command}"]
        cmd.append(f"{self.user}@{self.host}")
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            # give ssh a moment to fail fast (bad host/auth/port in use)
            time.sleep(1.5)
            if self._process.poll() is not None:
                lines = self._process.stderr.read().decode(errors="replace").strip().splitlines()
                self.last_error = lines[-1] if lines else "ssh exited"
                return False
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
            self._monitor_thread.start()
            return True
        except OSError as e:
            self.last_error = str(e)
            return False

    def stop(self):
        self._running = False
        if self._process and self._process.poll() is None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except Exception:
                self._process.terminate()
        self._process = None

    def _monitor(self):
        while self._running and self._process:
            if self._process.poll() is not None:
                self._running = False
                if self._on_disconnect:
                    self._on_disconnect()
                break
            time.sleep(3)
