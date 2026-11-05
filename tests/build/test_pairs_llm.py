"""Mapping pairs (batch2b section 11) and the two build LLM hand fixes (output cap, structured output method)."""
import json

from governor.build import design, llm as build_llm
from governor.build.llm import FakeBuildLLM, OpenRouterLLM
from governor.build.models import Proposal, ProposalReply, proposal_as_reply
from governor.core.catalogue import load_blueprint, load_kpis
from governor.core import paths

KPIS = load_kpis(paths.KNOWLEDGE / "kpis.yaml")
BLUEPRINT = load_blueprint(paths.KNOWLEDGE / "blueprint.md")


def _as_pairs(good: dict) -> dict:
    """The json_schema-shaped reply: every KPI mapping as a list of {name, value} pairs, no dict."""
    reply = proposal_as_reply(good)
    assert all("mapping" not in k for k in reply["kpis"])
    return reply


def test_schema_seen_by_the_model_has_pairs_not_a_free_form_object():
    schema = json.dumps(ProposalReply.model_json_schema())
    assert "mapping_pairs" in schema and '"mapping"' not in schema
    pair = ProposalReply.model_json_schema()["$defs"]["MappingPair"]
    assert set(pair["required"]) == {"name", "value"}


def test_pairs_become_the_full_mapping(good):
    reply = ProposalReply.model_validate_json(json.dumps(_as_pairs(good)))
    prop = reply.to_proposal()
    assert prop.to_json_dict() == Proposal.model_validate(good).to_json_dict()
    gmv = next(k for k in prop.kpis if k.id == "gmv")
    assert gmv.mapping == next(k for k in good["kpis"] if k["id"] == "gmv")["mapping"] and len(gmv.mapping) >= 2


def test_propose_converts_a_pairs_reply_before_validation(profile, good):
    fake = FakeBuildLLM({"propose": [json.dumps(_as_pairs(good))]})
    prop = design.propose(profile, KPIS, BLUEPRINT, [], fake)
    assert isinstance(prop, Proposal)
    assert {k.id: k.mapping for k in prop.kpis} == {k["id"]: k.get("mapping", {}) for k in good["kpis"]}
    assert "mapping_pairs" in fake.prompts[0][1]


def test_a_dict_reply_is_still_accepted(profile, good):
    prop = design.propose(profile, KPIS, BLUEPRINT, [], FakeBuildLLM({"propose": [json.dumps(good)]}))
    assert prop.to_json_dict() == Proposal.model_validate(good).to_json_dict()


def test_previous_proposal_is_shown_as_pairs(profile, good):
    text = design.build_prompt(profile, KPIS, BLUEPRINT, [], previous=good, note="fix it")
    prev = text.split("## Your previous proposal", 1)[1]
    assert "mapping_pairs" in prev and '"mapping":' not in prev


# ---- the hand fixes in build/llm.py ----

class _Client:
    def __init__(self):
        self.max_tokens, self.methods = None, []

    def with_structured_output(self, schema, method, include_raw):
        self.methods.append(method)
        client = self

        class _Runnable:
            def invoke(self, prompt):
                return {"raw": None, "parsed": schema.model_validate({}), "parsing_error": None}

        assert include_raw and client
        return _Runnable()


def _patch(monkeypatch):
    client = _Client()
    import governor.core.llm as core_llm

    monkeypatch.setattr(core_llm, "get_chat_model", lambda **kw: client)
    monkeypatch.setattr(core_llm, "usage_from_message", lambda m: {"input_tokens": 0, "output_tokens": 0})
    return client


def test_max_tokens_default_and_env(monkeypatch):
    client = _patch(monkeypatch)
    monkeypatch.delenv(build_llm.MAX_TOKENS_ENV, raising=False)
    OpenRouterLLM("p", "w")._client("plan")
    assert client.max_tokens == 32000
    monkeypatch.setenv(build_llm.MAX_TOKENS_ENV, "1234")
    OpenRouterLLM("p", "w")._client("plan")
    assert client.max_tokens == 1234


def test_structured_method_default_and_env(monkeypatch):
    client = _patch(monkeypatch)
    monkeypatch.delenv(build_llm.STRUCTURED_METHOD_ENV, raising=False)
    OpenRouterLLM("p", "w").structured("propose", "x", ProposalReply)
    monkeypatch.setenv(build_llm.STRUCTURED_METHOD_ENV, "function_calling")
    OpenRouterLLM("p", "w").structured("propose", "x", ProposalReply)
    assert client.methods == ["json_schema", "function_calling"]
