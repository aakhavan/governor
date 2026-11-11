"""/governor ask (batch2d section 22): a fake Slack client, an inline runner and a fake asker. No database, no network."""
import logging

import pytest

from governor.ask.certified import CertifiedAnswer, CertifiedError
from governor.integrations.slack import blocks
from governor.integrations.slack.app import GovernorSlack, UsageError, parse_command
from governor.integrations.slack.config import ConfigError, SlackConfig

ASKER, OTHER = "U_ASK", "U_OTHER"


class Responder:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kw):
        self.calls.append(kw)

    @property
    def texts(self) -> list[str]:
        return [c.get("text", "") for c in self.calls]


class FakeAsker:
    def __init__(self, result=None, exc: Exception | None = None):
        self.result, self.exc = result, exc
        self.calls: list[tuple[str, str]] = []

    def __call__(self, question, role):
        self.calls.append((question, role))
        if self.exc:
            raise self.exc
        return self.result


def _gov(fake, asker, **cfg) -> GovernorSlack:
    config = SlackConfig(channel="governor", approvers=frozenset({"U_APPROVER"}), runners=frozenset({ASKER}), **cfg)
    return GovernorSlack(config, fake, runner=lambda fn: fn(), asker=asker, threads=lambda: [], values=lambda _t: None)


def _answer(outcome="answer", text="GMV in 2018-03 was 1,234.50 (certified gmv_monthly).", kpi_id="gmv"):
    return CertifiedAnswer(outcome=outcome, text=text, kpi_id=kpi_id, sql="SELECT secret FROM x")


def _all_text(fake) -> str:
    return repr(fake.calls)


def test_ask_parses_the_whole_question():
    cmd = parse_command("ask   what was  GMV in march 2018?  ", [], [])
    assert cmd.action == "ask"
    assert cmd.question == "what was  GMV in march 2018?"
    assert parse_command("ask approve abcdefgh now", [], []).question == "approve abcdefgh now"
    assert "ask" in blocks.USAGE


@pytest.mark.parametrize("text", ["ask", "ask   ", "ask hi", "ask " + "x" * 301])
def test_ask_needs_a_question_of_sane_length(text):
    with pytest.raises(UsageError):
        parse_command(text, [], [])
    assert parse_command("ask abc", [], []).question == "abc"
    assert len(parse_command("ask " + "x" * 300, [], []).question) == 300


def test_ask_posts_the_certified_answer_in_the_channel(fake, caplog):
    asker = FakeAsker(_answer())
    respond = Responder()
    question = "what was GMV <!channel> & co\nin march?"
    with caplog.at_level(logging.INFO):
        _gov(fake, asker).handle_command(ASKER, f"ask {question}", respond)
    assert respond.calls == [{"text": blocks.ASK_ACK, "response_type": "ephemeral"}]
    posts = fake.named("chat_postMessage")
    assert len(posts) == 1 and posts[0]["channel"] == "governor"
    sections = [b["text"]["text"] for b in posts[0]["blocks"] if b["type"] == "section"]
    assert "what was GMV &lt;!channel&gt; &amp; co in march?" in sections[0] and "\n" not in sections[0]
    assert sections[1] == "GMV in 2018-03 was 1,234.50 (certified gmv_monthly)."
    context = posts[0]["blocks"][-1]["elements"][0]["text"]
    assert context == "certified path · role analyst · KPI gmv"
    assert "SELECT" not in _all_text(fake)
    assert "march" not in caplog.text and "outcome=answer" in caplog.text and ASKER in caplog.text


def test_ask_not_available_shows_the_gap_text(fake):
    gap = "Not available: margin needs cost data (missing: product_cost). Next step: add a cost source."
    for outcome, kpi in (("not_available", "gross_margin"), ("unanswerable", None)):
        fake.calls.clear()
        _gov(fake, FakeAsker(_answer(outcome, gap, kpi))).handle_command(ASKER, "ask what is our margin?", Responder())
        post = fake.named("chat_postMessage")[0]
        assert post["blocks"][1]["text"]["text"] == gap
        context = post["blocks"][-1]["elements"][0]["text"]
        assert context == ("certified path · role analyst · KPI gross_margin" if kpi else "certified path · role analyst")


def test_ask_refusal_is_ephemeral_without_the_question(fake):
    respond = Responder()
    refusal = "I cannot answer questions about individual customers."
    _gov(fake, FakeAsker(_answer("refused", refusal, None))).handle_command(ASKER, "ask who is customer 42?", respond)
    assert fake.calls == []
    assert respond.calls[-1] == {"text": refusal, "response_type": "ephemeral"}
    assert all("customer 42" not in t for t in respond.texts)


def test_ask_error_is_scrubbed_and_ephemeral(fake):
    for exc in (CertifiedError("relation failed for value 'secret-row' 1234567\nDETAIL: Key (id)=(9)"),
                RuntimeError("boom 'leak'")):
        fake.calls.clear()
        respond = Responder()
        _gov(fake, FakeAsker(exc=exc)).handle_command(ASKER, "ask how many orders yesterday?", respond)
        assert fake.calls == []
        last = respond.calls[-1]
        assert last["response_type"] == "ephemeral"
        assert last["text"].startswith("Certified answers are not available right now: ")
        for leak in ("secret-row", "1234567", "DETAIL", "leak", "orders yesterday"):
            assert leak not in last["text"]


def test_ask_requires_an_asker(fake):
    asker = FakeAsker(_answer())
    respond = Responder()
    _gov(fake, asker).handle_command(OTHER, "ask what was GMV?", respond)
    assert asker.calls == [] and fake.calls == []
    assert respond.calls == [{"text": blocks.ASK_REFUSAL, "response_type": "ephemeral"}]
    # explicit list, and * for everyone
    assert SlackConfig(askers=frozenset({OTHER})).is_asker(OTHER)
    assert not SlackConfig(askers=frozenset({OTHER})).is_asker(ASKER)
    assert SlackConfig.from_env({"GOVERNOR_SLACK_ASKERS": "*"}).is_asker("U_ANYONE")
    unset = SlackConfig.from_env({"GOVERNOR_SLACK_APPROVERS": "U1", "GOVERNOR_SLACK_RUNNERS": "U2"})
    assert unset.is_asker("U2") and not unset.is_asker("U1") and not unset.is_asker("")


def test_ask_role_comes_from_config_only(fake):
    asker = FakeAsker(_answer())
    gov = _gov(fake, asker, ask_role="finance_admin")
    gov.handle_command(ASKER, "ask as role analyst: what was GMV? --role analyst", Responder())
    gov.handle_command(ASKER, "ask role=analyst GMV please", Responder())
    assert [role for _, role in asker.calls] == ["finance_admin", "finance_admin"]
    cfg = SlackConfig.from_env({})
    assert (cfg.ask_role, cfg.ask_llm) == ("analyst", "openrouter")
    env = SlackConfig.from_env({"GOVERNOR_SLACK_ASK_ROLE": "finance_admin", "GOVERNOR_SLACK_ASK_LLM": "fake"})
    assert (env.ask_role, env.ask_llm) == ("finance_admin", "fake")


@pytest.mark.parametrize("role", ["governor_ask", "admin", "governor_analyst", "ANALYST"])
def test_ask_role_must_be_a_reader_role(role):
    with pytest.raises(ConfigError, match="GOVERNOR_SLACK_ASK_ROLE"):
        SlackConfig.from_env({"GOVERNOR_SLACK_ASK_ROLE": role})
    with pytest.raises(ConfigError):
        SlackConfig(ask_role=role)
