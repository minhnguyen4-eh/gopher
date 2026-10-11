import time

import pytest

from gopher.core import config, controller, pac
from gopher.core.pac_server import PacServer


def test_pac_matches_apex_and_subdomains_and_uses_port():
    text = pac.render(["discord.com"], 1081)
    assert '["discord.com"]' in text
    assert "127.0.0.1:1081" in text
    assert 'dnsDomainIs(host, "." + domains[i])' in text


def test_validate_normalises_domains():
    cfg = config.validate({"domains": ["*.Discord.com", " discord.com ", ""]}, config.DEFAULT)
    assert cfg["domains"] == ["discord.com"]


@pytest.mark.parametrize("raw", [{"local_port": 70000}, {"ssh_port": 0}, {"domains": ["bad domain"]}])
def test_validate_rejects_bad_input(raw):
    with pytest.raises(ValueError):
        config.validate(raw, config.DEFAULT)


class FakeTunnel:
    ok = True
    last_error = ""

    def __init__(self, **kw):
        pass

    def set_on_disconnect(self, cb):
        self.cb = cb

    def start(self):
        return self.ok

    def stop(self):
        pass


@pytest.fixture
def ctl(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "c.json"))
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(pac, "PAC_PATH", str(tmp_path / "g.pac"))
    monkeypatch.setattr(controller.proxy, "enable_pac", lambda path: True)
    monkeypatch.setattr(controller.proxy, "disable_pac", lambda: True)
    c = controller.Controller(tunnel_factory=FakeTunnel)
    c._pac_server = PacServer(port=0)  # random port: never clash with a running Gopher
    c.cfg.update(ssh_host="h", ssh_user="u")
    return c


def wait_for(c, state):
    for _ in range(50):
        if c.state == state:
            return
        time.sleep(0.02)
    raise AssertionError(f"state {c.state!r}, wanted {state!r}")


def test_connect_disconnect(ctl):
    ctl.connect()
    wait_for(ctl, controller.CONNECTED)
    assert ctl.snapshot()["status"] == "Gopher Proxy: connected (h)"
    ctl.disconnect()
    assert ctl.state == controller.OFF


def test_connect_failure_sets_error(ctl):
    ctl.tunnel.ok = False
    ctl.connect()
    wait_for(ctl, controller.ERROR)


def test_connect_requires_config(ctl):
    ctl.cfg["ssh_host"] = ""
    with pytest.raises(controller.NotConfigured):
        ctl.connect()


@pytest.mark.parametrize("host,expected", [
    ("100.80.71.80", True), ("100.128.0.1", False), ("pc.tailca2a14.ts.net", True),
    ("example.com", False), ("192.168.1.1", False),
])
def test_is_tailnet_host(host, expected):
    assert controller.tailscale.is_tailnet_host(host) is expected


def test_tailnet_host_logs_in_before_tunnel(ctl, monkeypatch):
    calls = []
    monkeypatch.setattr(controller.tailscale, "ensure_ready", lambda: calls.append("ts"))
    ctl.cfg["ssh_host"] = "100.80.71.80"
    ctl.connect()
    wait_for(ctl, controller.CONNECTED)
    assert calls == ["ts"]


def test_tailscale_failure_sets_error_and_skips_tunnel(ctl, monkeypatch):
    def fail():
        raise controller.tailscale.TailscaleError("login not completed")
    monkeypatch.setattr(controller.tailscale, "ensure_ready", fail)
    ctl.cfg["ssh_host"] = "100.80.71.80"
    ctl.connect()
    wait_for(ctl, controller.ERROR)
    assert "login not completed" in ctl.snapshot()["status"]


def test_tunnel_failure_reports_reason(ctl):
    ctl.tunnel.ok = False
    ctl.tunnel.last_error = "bind [127.0.0.1]:1080: Address already in use"
    ctl.connect()
    wait_for(ctl, controller.ERROR)
    assert "Address already in use" in ctl.snapshot()["status"]


def test_reap_stale_tunnel_only_kills_our_ssh(monkeypatch):
    from gopher.core import tunnel
    killed = []
    cmds = {"11": "ssh -N -D 1080 -o X host", "12": "python server.py"}

    def fake_run(args, **kw):
        class R:
            stdout = "11\n12\n" if args[0] == "lsof" else cmds[args[-1]]
        return R()
    monkeypatch.setattr(tunnel.subprocess, "run", fake_run)
    monkeypatch.setattr(tunnel.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(tunnel.time, "sleep", lambda s: None)
    tunnel.reap_stale_tunnel(1080)
    assert killed == [11]


def test_pac_server_serves_rendered_pac():
    import urllib.request
    srv = PacServer(port=0)
    try:
        url = srv.start(lambda: pac.render(["discord.com"], 1080))
        assert url.startswith("http://127.0.0.1:") and url.endswith("/proxy.pac")
        with urllib.request.urlopen(url) as r:
            assert "127.0.0.1:1080" in r.read().decode()
    finally:
        srv.stop()


def test_connect_enables_http_pac_and_disconnect_stops_server(ctl, monkeypatch):
    urls = []
    monkeypatch.setattr(controller.proxy, "enable_pac", lambda url: urls.append(url))
    ctl.connect()
    wait_for(ctl, controller.CONNECTED)
    assert urls[0].startswith("http://127.0.0.1:") and urls[0].endswith("/proxy.pac")
    ctl.disconnect()
    assert ctl._pac_server._server is None
