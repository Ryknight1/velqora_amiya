"""Briefing side: Bifrost client, JSON handling, verification, assembly and schema validation."""
import asyncio

import pytest

from app.agents import briefing_agent, verification_agent as va
from app.agents.analysis_agent import extract_json_object, normalize_analysis, run_analysis
from app.exceptions import ExternalServiceError, ServiceNotConfigured, UpstreamAuthError
from app.services.bifrost_service import BifrostService
from app.services.http_client import HttpResponse
from app.utils import date_utils as du
from app.utils.source_utils import assign_ids, normalize_result
from app.utils.validation import build_entity
from tests.helpers import FakeTransport, json_response, make_settings, no_sleep, tav


def run(coro):
    return asyncio.run(coro)


def llm_reply(text, status=200):
    return json_response({"model": "testprovider/test-model", "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 100, "completion_tokens": 50}}, status)


# ---------------------------------------------------------------- Bifrost client
def test_bifrost_request_shape_and_auth_modes():
    t = FakeTransport(lambda *a: llm_reply("hello"))
    svc = BifrostService(make_settings(bifrost_api_key="k-123"), transport=t)
    out = run(svc.chat([{"role": "user", "content": "hi"}]))
    call = t.calls[0]
    assert out.text == "hello" and call["url"] == "http://bifrost.test/v1/chat/completions"
    assert call["json"]["model"] == "testprovider/test-model" and call["headers"]["Authorization"] == "Bearer k-123"
    vk = FakeTransport(lambda *a: llm_reply("x"))
    run(BifrostService(make_settings(bifrost_api_key="vk-1", bifrost_auth_mode="virtual_key"), transport=vk).chat([{"role": "user", "content": "hi"}]))
    assert vk.calls[0]["headers"]["x-bf-vk"] == "vk-1" and "Authorization" not in vk.calls[0]["headers"]
    v1 = FakeTransport(lambda *a: llm_reply("x"))                              # base URL already ending in /v1
    run(BifrostService(make_settings(bifrost_base_url="http://b.test/v1"), transport=v1).chat([{"role": "user", "content": "hi"}]))
    assert v1.calls[0]["url"] == "http://b.test/v1/chat/completions"


def test_bifrost_model_is_config_only():
    t = FakeTransport(lambda *a: llm_reply("x"))
    run(BifrostService(make_settings(bifrost_model="other/bigger-model"), transport=t).chat([{"role": "user", "content": "hi"}]))
    assert t.calls[0]["json"]["model"] == "other/bigger-model"


def test_bifrost_errors():
    msgs = [{"role": "user", "content": "hi"}]
    with pytest.raises(ServiceNotConfigured):
        run(BifrostService(make_settings(bifrost_model=""), transport=FakeTransport(lambda *a: None)).chat(msgs))
    with pytest.raises(UpstreamAuthError):
        run(BifrostService(make_settings(), transport=FakeTransport(lambda *a: HttpResponse(401)), sleep=no_sleep).chat(msgs))
    with pytest.raises(ExternalServiceError):
        run(BifrostService(make_settings(), transport=FakeTransport(lambda *a: json_response({"error": {"message": "model not found"}}, 404)), sleep=no_sleep).chat(msgs))
    with pytest.raises(ExternalServiceError):
        run(BifrostService(make_settings(), transport=FakeTransport(lambda *a: json_response({"choices": []})), sleep=no_sleep).chat(msgs))
    seq = iter([HttpResponse(503), llm_reply("ok")])
    assert run(BifrostService(make_settings(), transport=FakeTransport(lambda *a: next(seq)), sleep=no_sleep).chat(msgs)).text == "ok"


def test_bifrost_health():
    def handler(method, url, body):
        return json_response({"data": [{"id": "testprovider/test-model"}]}) if url.endswith("/v1/models") else json_response({})
    info = run(BifrostService(make_settings(), transport=FakeTransport(handler)).health())
    assert info["status"] == "ok" and info["model_listed"] is True
    assert run(BifrostService(make_settings(bifrost_base_url=""), transport=FakeTransport(handler)).health())["status"] == "not_configured"


# ---------------------------------------------------------------- JSON extraction / normalisation
def test_extract_json_object_variants():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json_object('Sure! {"a": [1,2,],} thanks') == {"a": [1, 2]}
    for bad in ("no json here", "[1,2]", '{"a": '):
        with pytest.raises(ValueError):
            extract_json_object(bad)


def test_normalize_analysis_is_defensive():
    raw = {"overview": "Aurelia builds routing software.", "key_people": [{"name": "Maya Chen", "title": "CEO", "source_ids": "S1, S9"}, "junk"],
           "recent_developments": [{"claim": "Aurelia raised money in a Series B round.", "sources": ["s2", "[S3]", "S99"]}],
           "industry_tags": ["Logistics", "logistics", "x", "Freight tech"], "suggested_questions": None, "bogus": 1}
    out = normalize_analysis(raw, {"S1", "S2", "S3"})
    assert out["overview"] == [{"text": "Aurelia builds routing software.", "source_ids": []}]
    assert out["key_people"] == [{"name": "Maya Chen", "role": "CEO", "source_ids": ["S1"]}]
    assert out["recent_developments"][0]["source_ids"] == ["S2", "S3"]
    assert out["industry_tags"] == ["Logistics", "Freight tech"] and out["suggested_questions"] == []


# ---------------------------------------------------------------- verification
def _sources():
    entity = build_entity("Aurelia Systems", "https://aurelia.example.com")
    start, end = du.research_window()
    raws = [
        tav("Aurelia Systems raises $40 million Series B", "https://www.reuters.com/a", "Aurelia Systems raised $40 million in Series B funding led by Northwind Capital.", 3),
        tav("About Aurelia Systems", "https://aurelia.example.com/about", "Aurelia Systems builds AI software that optimises freight routing for logistics companies. Maya Chen is the chief executive officer.", None),
        tav("Aurelia Systems opens Singapore office", "https://www.ft.com/b", "Aurelia Systems opened an office in Singapore.", 120),
    ]
    items = [normalize_result(r, category="news", entity=entity, retrieved_at="now", window_start=start, window_end=end) for r in raws]
    return entity, assign_ids(items)


def _verify(section, text, ids, **extra):
    _, sources = _sources()
    claim = {"claim_id": "C1", "section": section, "text": text, "source_ids": ids, **extra}
    return va.verify_all([claim], sources, 0.6)[0], sources


def test_verification_accepts_grounded_and_rejects_fabricated():
    ok, sources = _verify("recent_developments", "Aurelia Systems raised $40 million in Series B funding.", ["S1"])
    assert ok["verification_status"] == "verified" and sources[0]["supports_claims"] == ["C1"]
    wrong_number, _ = _verify("recent_developments", "Aurelia Systems raised $90 million in Series B funding.", ["S1"])
    assert wrong_number["verification_status"] == "unverified" and "90" in wrong_number["reason"]
    invented, _ = _verify("business_insights", "Aurelia Systems acquired Nimbus Robotics last week.", ["S1"])
    assert invented["verification_status"] == "unverified"


def test_verification_dates_and_attribution():
    undated, _ = _verify("recent_developments", "Aurelia Systems builds AI software that optimises freight routing.", ["S2"])
    assert undated["verification_status"] == "undated"                      # grounded, but not provably recent
    outdated, _ = _verify("recent_developments", "Aurelia Systems opened an office in Singapore.", ["S3"])
    assert outdated["verification_status"] == "outdated"
    overview, _ = _verify("overview", "Aurelia Systems builds AI software that optimises freight routing.", ["S2"])
    assert overview["verification_status"] == "verified"                    # background facts need no recency
    attributed, _ = _verify("overview", "Aurelia Systems builds AI software that optimises freight routing.", [])
    assert attributed["verification_status"] == "verified" and attributed["supporting_source_ids"] == ["S2"]
    miscited, _ = _verify("overview", "Aurelia Systems raised $40 million in Series B funding.", ["S2"])
    assert miscited["verification_status"] == "verified" and miscited["supporting_source_ids"] == ["S1"]   # wrong id, real support
    still_bad, _ = _verify("overview", "Aurelia Systems raised $90 million in Series B funding.", ["S2"])
    assert still_bad["verification_status"] == "unverified"
    bad_id, _ = _verify("overview", "Aurelia Systems raised $40 million in Series B funding.", ["S42"])
    assert bad_id["verification_status"] == "verified" and bad_id["supporting_source_ids"] == ["S1"]


def test_verification_people():
    good, _ = _verify("key_people", "Maya Chen, chief executive officer", ["S2"], name="Maya Chen", role="chief executive officer")
    assert good["verification_status"] == "verified"
    wrong_role, _ = _verify("key_people", "Maya Chen, chief financial officer", ["S2"], name="Maya Chen", role="chief financial officer")
    assert wrong_role["verification_status"] == "unverified"
    stranger, _ = _verify("key_people", "John Doe, chairman", ["S2"], name="John Doe", role="chairman")
    assert stranger["verification_status"] == "unverified"


# ---------------------------------------------------------------- briefing assembly
GOOD_LLM_JSON = """{
 "overview": [{"text": "Aurelia Systems builds AI software that optimises freight routing for logistics companies.", "source_ids": ["S2"]}],
 "key_people": [{"name": "Maya Chen", "role": "chief executive officer", "source_ids": ["S2"]}],
 "recent_developments": [
   {"text": "Aurelia Systems raised $40 million in Series B funding.", "source_ids": ["S1"]},
   {"text": "Aurelia Systems acquired Nimbus Robotics for $900 million.", "source_ids": ["S1"]},
   {"text": "Aurelia Systems builds AI software that optimises freight routing.", "source_ids": ["S2"]}],
 "business_insights": [], "industry_information": [], "industry_tags": ["Logistics tech"],
 "meeting_talking_points": [{"text": "Ask how the new Series B funding changes the product roadmap.", "basis_source_ids": ["S1"]}],
 "suggested_questions": [{"text": "What does the funding mean for hiring plans this year?"}],
 "potential_risks": [{"text": "Fresh funding may shift priorities away from smaller partners.", "basis_source_ids": ["S1"]}],
 "opportunities": [], "open_questions": [{"text": "Who are Aurelia's main enterprise customers?"}]
}"""


def _assemble(llm_text=GOOD_LLM_JSON, with_llm=True):
    entity, sources = _sources()
    window = du.research_window()
    analysis = None
    if with_llm:
        svc = BifrostService(make_settings(), transport=FakeTransport(lambda *a: llm_reply(llm_text)))
        analysis = run(run_analysis(entity, sources, window, svc, make_settings()))["analysis"]
    claims = va.make_claims(analysis) if analysis else []
    verified = va.verify_all(claims, sources, 0.6)
    draft = briefing_agent.build_briefing(research_id="a" * 32, briefing_id="b" * 32, entity=entity, window=window, sources=sources,
                                          analysis=analysis, verified=verified, model="m", warnings=[])
    return draft


def test_briefing_separates_verified_unverified_undated_and_ai_analysis():
    b = _assemble()
    assert [i["text"] for i in b["recent_developments"]] == ["Aurelia Systems raised $40 million in Series B funding."]
    assert any("Nimbus" in i["text"] for i in b["unverified_claims"])
    assert not any("Nimbus" in i["text"] for sec in ("recent_developments", "overview_items", "business_insights") for i in b[sec])
    assert any("freight routing" in i["text"] for i in b["undated_information"])      # grounded but undated -> not "recent"
    assert b["overview"].startswith("Aurelia Systems builds") and b["key_people"][0]["name"] == "Maya Chen"
    assert all(i["kind"] == "analysis" and i["verification_status"] == "analysis" for i in b["meeting_talking_points"] + b["potential_risks"])
    s = b["verification_summary"]
    assert (s["verified_claims"], s["unverified_claims"], s["undated_claims"], s["total_claims"]) == (3, 1, 1, 5)
    assert all(i["source_ids"] for i in b["recent_developments"])
    by_id = {x["source_id"]: x for x in b["sources"]}
    assert by_id["S1"]["verification_status"] == "verified" and by_id["S2"]["verification_status"] == "verified"
    assert by_id["S3"]["date_status"] == "out_of_window"
    assert all(n["date"] and n["source_ids"] for n in b["important_news"])           # AI-free, dated, in-window only
    assert "Singapore" not in " ".join(n["text"] for n in b["important_news"])


def test_briefing_without_llm_is_honest_not_fabricated():
    b = _assemble(with_llm=False)
    assert b["ai"]["analysis_available"] is False and b["meeting_talking_points"] == [] and b["overview"] == ""
    assert b["recent_developments"] and all(i["origin"] == "source_headline" for i in b["recent_developments"])
    assert any(o["kind"] == "unavailable" for o in b["open_questions"])


def test_briefing_with_no_sources_reports_gap():
    entity = build_entity("Nobody Known")
    draft = briefing_agent.build_briefing(research_id="a" * 32, briefing_id="b" * 32, entity=entity, window=du.research_window(),
                                          sources=[], analysis=None, verified=[], model=None, warnings=[])
    assert draft["sources"] == [] and draft["verification_summary"]["total_claims"] == 0
    assert "No relevant sources" in draft["open_questions"][0]["text"]


def test_briefing_matches_pydantic_schema():
    pytest.importorskip("pydantic")
    from app.schemas.briefing_schema import Briefing
    model = Briefing.model_validate(_assemble())
    dumped = model.model_dump()
    assert dumped["research_period"]["start_date"] and dumped["verification_summary"]["total_claims"] == 5
    assert Briefing.model_validate(dumped).briefing_id == "b" * 32


def test_invalid_llm_json_retries_then_fails_cleanly():
    entity, sources = _sources()
    t = FakeTransport(lambda *a: llm_reply("I cannot comply"))
    svc = BifrostService(make_settings(), transport=t)
    with pytest.raises(ExternalServiceError):
        run(run_analysis(entity, sources, du.research_window(), svc, make_settings(llm_json_retries=1)))
    assert len(t.calls) == 2                                                          # one retry only
    prompt = t.calls[0]["json"]["messages"]
    assert "untrusted" in prompt[0]["content"].lower() and "<source id=\"S1\"" in prompt[1]["content"]
