import time

import pytest

from gopher.core import config, controller, pac


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
