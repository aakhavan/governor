"""F6: one Slack bot for several tenants (batch3.md section 32). Offline: the fake Slack client, an inline runner and
a fake build object that records which tenant each call received."""
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from governor.build import graph
from governor.integrations.slack import __main__ as slack_main
from governor.integrations.slack import blocks
from governor.integrations.slack.app import GovernorSlack
from governor.integrations.slack.config import TARGETS_IGNORED, SlackConfig

APPROVER = "U_AMIR"
T_ACME = "aaaa1111-0000-4000-8000-000000000001"
T_GLOBEX = "bbbb2222-0000-4000-8000-000000000002"
SECRETS = ("s3cret-pw", "governor_build_local", "xoxb-", "xapp-", "password", "user=")


def _root(path: Path) -> None:
    k = path / "knowledge"
    k.mkdir(parents=True)
    (k / "kpis.yaml").write_text("version: 1\nkpis: []\n", encoding="utf-8")
    (k / "blueprint.md").write_text("---\nversion: 1\n---\n", encoding="utf-8")


@pytest.fixture
def registry(tmp_path) -> Path:
    for name in ("acme", "globex-eu"):
        _root(tmp_path / "tenants" / name)
    path = tmp_path / "tenants.yaml"
    path.write_text("tenants:\n"
                    "  acme: {root: tenants/acme, target: targets/acme, pg_port: 55432}\n"
                    "  globex-eu: {root: tenants/globex-eu, target: targets/globex-eu, pg_port: 55433, pg_db: shop2}\n",
                    encoding="utf-8")
    return path


def _config(registry: Path, **kw) -> SlackConfig:
    env = {"GOVERNOR_TENANTS": str(registry), "GOVERNOR_SLACK_APPROVERS": APPROVER,
           "GOVERNOR_SLACK_NAMES": f"{APPROVER}=Amir Akhavan", "GOVERNOR_SLACK_LLM": "fake:none", **kw}
    return SlackConfig.from_env(env)


def _checkpoints(path: Path, *thread_ids: str) -> None:
    """A tenant's checkpoint file holding these build threads (only what ``known_threads`` reads)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("create table if not exists checkpoints (thread_id text)")
        conn.executemany("insert into checkpoints values (?)", [(t,) for t in thread_ids])
        conn.commit()
    finally:
        conn.close()


class FakeBuild:
    """Records (call, tenant name, args) for start, approve and reject."""

    def __init__(self):
        self.calls: list[tuple[str, str | None, tuple]] = []

    @staticmethod
    def _name(tenant) -> str | None:
        return tenant.name if tenant is not None else None

    def start(self, target, project, llm, *, thread_id=None, tenant=None, **kw):
        self.calls.append(("start", self._name(tenant), (Path(target), project, thread_id)))
        return {"status": graph.AWAITING, "thread_id": thread_id}

    def approve(self, thread_id, by, llm, *, tenant=None, **kw):
        self.calls.append(("approve", self._name(tenant), (thread_id, by)))
        return {"status": graph.BUILT}

    def reject(self, thread_id, note, llm, *, tenant=None, **kw):
        self.calls.append(("reject", self._name(tenant), (thread_id, note)))
        return {"status": graph.AWAITING}


class Responder:
    def __init__(self):
        self.said: list[dict] = []

    def __call__(self, **kw):
        self.said.append(kw)

    @property
    def text(self) -> str:
        return "\n".join(s.get("text", "") for s in self.said)


def _inline(fn):
    fn()


def _gov(config, client, build, **kw) -> GovernorSlack:
    return GovernorSlack(config, client, runner=_inline, llm_factory=lambda spec: object(), build=build, **kw)


def _texts(client) -> str:
    """Every text and block text the bot sent."""
    out = []
    for _, kw in client.calls:
        out.append(str(kw.get("text") or ""))
        for b in kw.get("blocks") or []:
            out.append(str((b.get("text") or {}).get("text") or ""))
            out.extend(str(e.get("text") or "") for e in b.get("elements") or [] if isinstance(e, dict))
    return "\n".join(out)


def test_targets_come_from_tenant_registry(registry, tmp_path, monkeypatch, capsys):
    config = _config(registry, GOVERNOR_SLACK_TARGETS=f"olist={tmp_path / 'olist'}")
    tenants = config.tenants
    assert sorted(config.targets) == ["acme", "globex-eu"]
    assert config.targets == {n: t.target for n, t in tenants.items()}
    assert config.warnings == (TARGETS_IGNORED,)
    assert _config(registry).warnings == ()  # no GOVERNOR_SLACK_TARGETS: no warning
    # without the registry nothing changes
    single = SlackConfig.from_env({"GOVERNOR_SLACK_TARGETS": f"olist={tmp_path / 'olist'}"})
    assert list(single.targets) == ["olist"] and single.tenants == {} and single.warnings == ()

    # the start-up warning and the start-up line with each tenant and its database
    monkeypatch.setenv("GOVERNOR_BUILD_PASSWORD", "s3cret-pw")
    for k, v in {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_APP_TOKEN": "xapp-test", "GOVERNOR_SLACK_APPROVERS": APPROVER,
                 "GOVERNOR_TENANTS": str(registry), "GOVERNOR_SLACK_TARGETS": f"olist={tmp_path / 'olist'}"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(slack_main, "create_app", lambda config: object())
    import slack_bolt.adapter.socket_mode as sm

    monkeypatch.setattr(sm, "SocketModeHandler", lambda app, token: SimpleNamespace(start=lambda: None))
    assert slack_main.main() == 0
    err = capsys.readouterr().err
    assert TARGETS_IGNORED in err
    line = next(ln for ln in err.splitlines() if "Socket Mode" in ln)
    assert "acme: localhost:55432/shop" in line and "globex-eu: localhost:55433/shop2" in line
    assert "olist" not in line
    for secret in SECRETS:
        assert secret not in line, secret

    # a broken registry is a configuration error naming the variable
    bad = tmp_path / "bad.yaml"
    bad.write_text("tenants: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="GOVERNOR_TENANTS"):
        SlackConfig.from_env({"GOVERNOR_TENANTS": str(bad)})


def test_run_routes_to_its_tenant(registry, fake):
    config = _config(registry)
    build = FakeBuild()
    gov = _gov(config, fake, build, tenant_threads=lambda: {"acme": [], "globex-eu": []})
    said = Responder()
    gov.handle_command(APPROVER, "run globex-eu", said)
    assert len(build.calls) == 1
    call, tenant, (target, project, thread_id) = build.calls[0]
    globex = config.tenants["globex-eu"]
    assert (call, tenant, target, project) == ("start", "globex-eu", globex.target, "globex-eu")
    assert "tenant `globex-eu`" in said.text and blocks.short(thread_id) in said.text
    # the target became a dbt project with a valid dbt name; the other tenant's target is untouched
    assert "name: globex_eu" in (globex.target / "dbt_project.yml").read_text(encoding="utf-8")
    assert not config.tenants["acme"].target.exists()

    gov.handle_command(APPROVER, "run acme force", said)
    assert build.calls[1][:2] == ("start", "acme") and build.calls[1][2][0] == config.tenants["acme"].target

    # an unknown name (or a GOVERNOR_SLACK_TARGETS name) is a usage error; nothing runs
    said = Responder()
    gov.handle_command(APPROVER, "run olist", said)
    assert len(build.calls) == 2 and "known target" in said.text


def test_approve_resolves_tenant_from_thread(registry, fake, tmp_path):
    config = _config(registry)
    acme, globex = config.tenants["acme"], config.tenants["globex-eu"]
    _checkpoints(acme.checkpoints, T_ACME)  # the real per-tenant checkpoint files, read by the default lister
    _checkpoints(globex.checkpoints, T_GLOBEX)
    build = FakeBuild()
    published: list[Path] = []
    gov = _gov(config, fake, build, values=lambda tid: {"status": graph.AWAITING},
               publisher=lambda target, open_pr=False: published.append(Path(target)) or {"status": "published"})

    gov.handle_command(APPROVER, f"approve {T_GLOBEX[:8]}", Responder())
    gov.handle_command(APPROVER, f"reject {T_ACME[:8]} split the orders model", Responder())
    said = Responder()
    gov.handle_approve_button(APPROVER, T_ACME, said)
    assert [(c, t, a[0]) for c, t, a in build.calls] == [
        ("approve", "globex-eu", T_GLOBEX), ("reject", "acme", T_ACME), ("approve", "acme", T_ACME)]
    assert "(tenant acme)" in said.text

    gov.handle_command(APPROVER, f"publish {T_GLOBEX[:8]}", Responder())
    assert published == [globex.target]

    # a thread no tenant holds is unknown
    said = Responder()
    gov.handle_command(APPROVER, "approve cccc3333", said)
    assert "Unknown build thread" in said.text and len(build.calls) == 3


def test_thread_in_two_tenants_is_a_usage_error(registry, fake):
    config = _config(registry)
    t1, t2 = "abcdef12-0000-4000-8000-00000000000a", "abcdef12-0000-4000-8000-00000000000b"
    build = FakeBuild()
    gov = _gov(config, fake, build, tenant_threads=lambda: {"acme": [t1, T_ACME], "globex-eu": [t2]},
               values=lambda tid: {"status": graph.AWAITING})
    for text in ("approve abcdef12", "publish abcdef12", "reject abcdef12 note"):
        said = Responder()
        gov.handle_command(APPROVER, text, said)
        assert "`acme`" in said.text and "`globex-eu`" in said.text, text
        assert said.said[0]["response_type"] == "ephemeral"
    assert build.calls == []
    # the full id is not ambiguous
    gov.handle_command(APPROVER, f"approve {t2}", Responder())
    assert build.calls == [("approve", "globex-eu", (t2, "Amir Akhavan"))]

    # a button whose thread is in both tenants changes nothing
    gov2 = _gov(config, fake, build, tenant_threads=lambda: {"acme": [T_ACME], "globex-eu": [T_ACME]},
                values=lambda tid: {"status": graph.AWAITING})
    said = Responder()
    gov2.handle_approve_button(APPROVER, T_ACME, said)
    assert "`acme`" in said.text and "`globex-eu`" in said.text and len(build.calls) == 1


def test_ask_refused_in_multi_tenant_mode(registry, fake):
    asked = []
    ran = []
    gov = GovernorSlack(_config(registry, GOVERNOR_SLACK_ASKERS="*"), fake, runner=lambda fn: ran.append(fn),
                        asker=lambda q, role: asked.append(q), build=FakeBuild(), tenant_threads=lambda: {})
    said = Responder()
    gov.handle_command(APPROVER, "ask what was revenue last month?", said)
    assert said.said == [{"text": "ask serves one tenant only; it is not available in multi-tenant mode yet",
                          "response_type": "ephemeral"}]
    assert asked == [] and ran == [] and fake.calls == []


def test_messages_name_the_tenant(registry, fake, good):
    config = _config(registry)
    gov = _gov(config, fake, FakeBuild(), tenant_threads=lambda: {"acme": [T_ACME], "globex-eu": [T_GLOBEX]},
               values=lambda tid: {"status": graph.AWAITING, "proposal": good, "findings": []})
    n = gov.notifier
    n.handle({"kind": "run_started", "thread_id": T_ACME, "project": "acme"})
    n.handle({"kind": "profiled", "thread_id": T_ACME})
    n.handle({"kind": "design_gate", "thread_id": T_ACME, "status": graph.AWAITING})
    progress = fake.named("chat_postMessage")[0]
    assert "tenant acme" in progress["text"] and "tenant acme" in progress["blocks"][0]["text"]["text"]
    assert all("tenant acme" in u["text"] for u in fake.named("chat_update"))
    card = fake.named("chat_postMessage")[1]
    assert "tenant acme" in card["text"] and "tenant acme" in card["blocks"][0]["text"]["text"]

    # replies under the thread (from the app and from the notifier) carry the tenant
    gov.handle_approve_button(APPROVER, T_ACME, Responder())
    n.handle({"kind": "repair", "thread_id": T_ACME, "repairs": 1, "models": ["silver_orders"]})
    replies = [kw for kw in fake.named("chat_postMessage")[2:]]
    assert replies and all("tenant acme" in kw["text"] for kw in replies)
    assert all(kw["blocks"][-1] == {"type": "context", "elements": [{"type": "mrkdwn", "text": "tenant acme"}]}
               for kw in replies)
    assert "globex" not in _texts(fake)

    # the usage footer lists each tenant and its database
    said = Responder()
    gov.handle_command(APPROVER, "", said)
    footer = said.text.splitlines()[-1]
    assert footer == "tenants: acme: localhost:55432/shop, globex-eu: localhost:55433/shop2"
