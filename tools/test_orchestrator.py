"""Checks for the Orchestrator (auto-routing of a turn). Run from merged/:  python tools/test_orchestrator.py
Runs Validate turn and Route turn JS in Node with stubs; writes nothing."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_restorer_agent import NODES, WF, into, run_js  # noqa: E402

ROUTE = NODES["Route turn"]["parameters"]["jsCode"]
TURN = {"session_id": "0" * 8 + "-0000-0000-0000-" + "0" * 12, "case_id": "case_widows_supper"}


def route(message, llm=None, agent="auto", image_type=None, region=None):
    """llm: the agent name Groq returns, 'junk' for unparseable output, None for a failed call."""
    groq = {"error": {"message": "429"}} if llm is None else {"choices": [{"message": {"content":
           "not json" if llm == "junk" else json.dumps({"agent": llm, "reason": "because"})}}]}
    v = {**TURN, "agent": agent, "message": message, "question": message, "image_type": image_type, "region": region}
    return run_js(ROUTE, groq, {"Check budget": v})[0]["json"]


def test_wiring():
    assert into("Auto?", "main") == ["Can act?"]
    assert into("Orchestrator", "main") == ["Auto?"]
    assert into("Route turn", "main") == ["Auto?", "Orchestrator"]
    assert into("Which expert?", "main") == ["Route turn"]
    o = NODES["Orchestrator"]
    assert o["onError"] == "continueRegularOutput" and o["alwaysOutputData"] is True  # failure falls back, never 500
    assert o["credentials"]["httpHeaderAuth"]["id"] == "fcGroqArchiv0001"
    assert "qwen/qwen3.8-27b" in o["parameters"]["jsonBody"]


def test_downstream_reads_routed_turn():
    # after routing, nothing may read the raw request's agent ('auto') from Check budget
    for n in WF["nodes"]:
        if n["name"] in ("Check budget", "Route turn"):
            continue
        assert "$('Check budget')" not in json.dumps(n["parameters"]), n["name"]


def test_llm_choice_is_used():
    r = route("Who owned it in 1950?", llm="archivist")
    assert (r["agent"], r["routed_by"], r["route_reason"]) == ("archivist", "llm", "because")


def test_bad_llm_output_falls_back_to_keywords():
    cases = {
        "What does the X-ray show under the table?": "restorer",
        "Is there retouching visible in UV?": "restorer",
        "Look at the brushwork near the signature": "restorer",
        "Was phenolformaldehyde available in 1907?": "scientist",
        "Is titanium white possible in 1921?": "scientist",
        "What pigment is the blue?": "scientist",
        "Who sold the painting at auction?": "archivist",
        "Is there a letter mentioning this work?": "archivist",
        "What about the gallery label on the stretcher?": "archivist",
        "Does this look like his other works from that year?": "curator",
        "I think it is a forgery, am I wrong?": "curator",
        "What should I do next?": "curator",
    }
    for q, want in cases.items():
        for llm in (None, "junk", "the judge"):  # failed call, unparseable, unknown expert
            r = route(q, llm=llm)
            assert r["agent"] == want and r["routed_by"] == "keywords", (q, llm, r["agent"])


def test_restorer_plate_choice():
    assert route("What do you see in UV?", llm="restorer", image_type="xray")["image_type"] == "uv"  # question wins
    assert route("What is in the marked area?", llm="restorer", image_type="xray")["image_type"] == "xray"  # on screen
    assert route("Any cracks?", llm="restorer")["image_type"] == "macro"  # default
    r = route("Who sold it?", llm="archivist", image_type="uv", region=[0.1, 0.1, 0.2, 0.2])
    assert r["image_type"] is None and r["region"] is None  # plate data only travels to the Restorer


def test_manual_pick_skips_orchestrator():
    r = route("anything", agent="scientist")
    assert (r["agent"], r["routed_by"]) == ("scientist", "player")


def test_validate_accepts_auto():
    js = NODES["Validate turn"]["parameters"]["jsCode"]
    ok = run_js(js, {"body": {**TURN, "agent": "auto", "message": "hi", "image_type": "uv", "region": [0, 0, .5, .5]}})[0]["json"]
    assert ok["ok"] and ok["image_type"] == "uv" and ok["region"] == [0, 0, .5, .5]
    assert run_js(js, {"body": {**TURN, "agent": "auto", "message": "hi"}})[0]["json"]["ok"]
    assert not run_js(js, {"body": {**TURN, "agent": "auto", "message": "hi", "image_type": "../x"}})[0]["json"]["ok"]
    assert not run_js(js, {"body": {**TURN, "agent": "judge", "message": "hi"}})[0]["json"]["ok"]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", t.__name__, "-", repr(e)[:300])
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
