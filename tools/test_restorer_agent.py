"""Checks for the Restorer agent build. Run from merged/:  python tools/test_restorer_agent.py
Builds the merged workflow in memory (writes nothing) and runs the Restorer's Code-node JS in Node with stubs."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_workflows as bw  # noqa: E402

WF = bw.merged()
bw.check(WF)
NODES = {n["name"]: n for n in WF["nodes"]}


def into(target, kind):
    """Names of nodes connected to `target` with connection type `kind`."""
    return sorted(src for src, kinds in WF["connections"].items()
                  for o in kinds.get(kind, []) for c in (o or []) if c["node"] == target)


def run_js(js, input_json, refs=None):
    """Run a Code node's JS with $input / $() stubbed; returns its result."""
    prelude = ("const $input = { first: () => ({ json: %s, binary: {} }), all: () => [{ json: %s, binary: {} }] };\n"
               "const REFS = %s; const $ = n => ({ first: () => ({ json: REFS[n] }) });\n") % (
        json.dumps(input_json), json.dumps(input_json), json.dumps(refs or {}))
    out = subprocess.run(["node", "-e", prelude + "console.log(JSON.stringify((function () {\n" + js + "\n})()));"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_agent_with_subnodes():
    a = NODES["Restorer - Restorer Agent"]
    assert a["type"] == "@n8n/n8n-nodes-langchain.agent"
    assert a["parameters"]["options"]["passthroughBinaryImages"] is True
    assert a["parameters"]["hasOutputParser"] is True
    assert into("Restorer - Restorer Agent", "ai_languageModel") == ["Restorer - Gemini Chat Model"]
    assert into("Restorer - Restorer Agent", "ai_memory") == ["Restorer - Restorer Memory"]
    assert into("Restorer - Restorer Agent", "ai_tool") == ["examine_plate", "plate_notes"]
    assert into("Restorer - Restorer Agent", "ai_outputParser") == ["Restorer - Findings format"]
    assert into("Restorer - Restorer Agent", "main") == ["Restorer - Agent input"]
    assert into("Restorer - Parse & Validate", "main") == ["Restorer - Restorer Agent"]


def test_notes_loaded_before_agent():
    # free tier is ~20 requests/day/model: the plate's notes come from Postgres up front, not via a tool call
    assert into("Restorer - Load plate notes", "main") == ["Restorer - Blocked?"]
    assert into("Restorer - Agent input", "main") == ["Restorer - Load plate notes"]
    assert "notes_text" in NODES["Restorer - Restorer Agent"]["parameters"]["options"]["systemMessage"]
    js = NODES["Restorer - Agent input"]["parameters"]["jsCode"]
    rows = [{"feature": "large oval form", "description": "Bright oval.", "x": 0.24, "y": 0.55, "r": 0.15},
            {"feature": "hidden forms", "description": "Forms that do not match.", "x": None, "y": None, "r": None}]
    out = run_js(js.replace("$('Restorer - Validate & Guardrail').first()", "({ json: REFS.g, binary: { plate: 1 } })"),
                 {"notes": rows}, {"g": {"case_id": "case_widows_supper", "image_type": "xray", "question": "q"}})[0]
    assert out["binary"] == {"plate": 1} and out["json"]["question"] == "q"
    # positions as words: the lite model echoed raw "x=0.07, y=0.4" to players despite the prompt
    assert "large oval form (middle left of the plate): Bright oval." in out["json"]["notes_text"]
    assert "x=" not in out["json"]["notes_text"] and "0.24" not in out["json"]["notes_text"]
    assert "hidden forms (whole plate)" in out["json"]["notes_text"]
    empty = run_js(js.replace("$('Restorer - Validate & Guardrail').first()", "({ json: {}, binary: {} })"), {"notes": []})[0]
    assert "no documented features" in empty["json"]["notes_text"]


def test_model_name_allows_images():
    m = NODES["Restorer - Gemini Chat Model"]["parameters"]["modelName"]
    # LangChain only sends images to gemini-2*/gemini-3* names; lite = its own, larger free daily quota
    assert m == "models/gemini-3.5-flash-lite", m
    url = NODES["Examine: build request"]["parameters"]["jsCode"]
    assert "models/gemini-3.1-flash-lite:generateContent" in url  # a second model = a second daily quota


def test_findings_schema_has_no_type_lists():
    # the parser's schema is sent to Gemini as a function declaration; Gemini rejects "type": [..] (400 Proto field)
    schema = json.loads(NODES["Restorer - Findings format"]["parameters"]["inputSchema"])
    bad = [k for k, v in schema["properties"].items() if isinstance(v.get("type"), list)]
    assert not bad, bad


def test_old_single_call_removed():
    for gone in ("Restorer - Build Gemini Request", "Restorer - Gemini Vision", "Plate to base64"):
        assert gone not in NODES, gone


def test_examine_plate_calls_own_subflow():
    t = NODES["examine_plate"]["parameters"]
    assert t["workflowId"]["value"] == bw.IDS["game"]
    assert set(t["workflowInputs"]["value"]) == {"case_id", "kind", "focus", "region"}
    trig = NODES["examine_plate request"]["parameters"]
    assert [v["name"] for v in trig["workflowInputs"]["values"]] == ["case_id", "kind", "focus", "region"]
    assert into("Examine: reply", "main") == ["Examine: Gemini Vision", "Examine: ok?"]


def test_memory_is_per_player_and_case():
    key = NODES["Restorer - Restorer Memory"]["parameters"]["sessionKey"]
    assert "session_id" in key and "case_id" in key and "$('Restorer - Validate & Guardrail')" in key


def test_retries_configured():
    # LangChain's Gemini client already retries 429/503 with backoff; an n8n retry on top re-ran the whole agent
    # (and its tool calls) up to 3x, burning the daily quota and keeping the player waiting minutes
    agent = NODES["Restorer - Restorer Agent"]
    assert not agent.get("retryOnFail"), "agent must not be retried by n8n"
    ex = NODES["Examine: Gemini Vision"]
    assert ex.get("retryOnFail") and ex.get("maxTries") == 2, ex.get("maxTries")


def test_plate_notes_tool_normalises_kind():
    q = NODES["plate_notes"]["parameters"]["query"]
    assert "x_ray" in q and "regexp_replace" in q, "the model writes 'X-ray', 'UV light'...: normalise in SQL"
    assert "x, y, r" not in q and "of the plate" in q, "positions as words, not raw numbers the model repeats"


def test_notes_in_system_message_not_replayed_by_memory():
    # memory stores the human message each turn: notes there would be replayed 6x; the system message is not stored
    p = NODES["Restorer - Restorer Agent"]["parameters"]
    assert "notes_text" not in p["text"] and "notes_text" in p["options"]["systemMessage"]
    assert p["options"]["systemMessage"].startswith("=")


def test_players_never_get_raw_coordinates():
    # live: the agent echoed the notes' "x=0.07, y=0.4" to the player
    sm = NODES["Restorer - Restorer Agent"]["parameters"]["options"]["systemMessage"]
    assert "never quote coordinates" in sm.lower()


def test_prompt_mentions_photo_only_when_attached():
    assert "has_photo" in NODES["Restorer - Restorer Agent"]["parameters"]["text"]
    js = NODES["Restorer - Agent input"]["parameters"]["jsCode"]
    stub = "({ json: {}, binary: %s })"
    with_photo = run_js(js.replace("$('Restorer - Validate & Guardrail').first()", stub % "{ plate: 1, photo: 2 }"), {"notes": []})[0]
    no_photo = run_js(js.replace("$('Restorer - Validate & Guardrail').first()", stub % "{ plate: 1 }"), {"notes": []})[0]
    assert with_photo["json"]["has_photo"] is True and no_photo["json"]["has_photo"] is False


def test_examine_check_more_spellings():
    js = NODES["Examine: check"]["parameters"]["jsCode"]
    for said, want in (("UV-fluorescence image", "uv"), ("raking light image", "raking_light"), ("X-ray photo", "xray")):
        got = run_js(js, {"case_id": "case_widows_supper", "kind": said, "focus": "", "region": ""})[0]["json"]
        assert got["ok"] and got["kind"] == want, (said, got)


def test_examine_reply_hides_provider_errors():
    js = NODES["Examine: reply"]["parameters"]["jsCode"]
    refs = {"Examine: check": {"ok": True, "kind": "uv", "focus": "left"}}
    out = run_js(js, {"error": {"message": "You exceeded your current quota, please check your plan and billing"}}, refs)[0]["json"]
    assert "quota" not in out["text"] and "billing" not in out["text"] and "could not be read" in out["text"]


def test_plate_notes_sql_updates_and_is_quiet():
    sql = (Path(__file__).resolve().parent.parent / "db" / "plate_notes.sql").read_text(encoding="utf-8")
    assert "client_min_messages" in sql, "NOTICE on re-run goes to stderr"
    assert "WHERE NOT EXISTS" not in sql and "DELETE FROM plate_notes" in sql, "edited notes must reach existing databases"


def test_setup_stops_when_plate_notes_fail():
    ps = (Path(__file__).resolve().parent.parent / "setup.ps1").read_text(encoding="utf-8")
    assert "plate_notes.sql failed" in ps and "$LASTEXITCODE" in ps


def test_setup_warns_when_restorer_credential_missing():
    ps = (Path(__file__).resolve().parent.parent / "setup.ps1").read_text(encoding="utf-8")
    assert "fcGeminiRestoAI1" in ps, "older installs without keys.env never get the new credential"


def test_all_code_nodes_parse():
    for n in WF["nodes"]:
        if n["type"] == "n8n-nodes-base.code":
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write("(async function () {\n" + n["parameters"]["jsCode"] + "\n})")
            out = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
            Path(f.name).unlink()
            assert out.returncode == 0, f"{n['name']}: {out.stderr}"


def test_examine_check_normalises_kind():
    js = NODES["Examine: check"]["parameters"]["jsCode"]
    ok = run_js(js, {"case_id": "case_widows_supper", "kind": "X-ray", "focus": "left", "region": "[0.1,0.2,0.3,0.4]"})[0]["json"]
    assert ok["ok"] and ok["kind"] == "xray" and ok["region"] == [0.1, 0.2, 0.3, 0.4]
    ok2 = run_js(js, {"case_id": "case_widows_supper", "kind": "raking light", "focus": "", "region": "null"})[0]["json"]
    assert ok2["ok"] and ok2["kind"] == "raking_light" and ok2["region"] is None
    for said, want in (("UV light", "uv"), ("X-ray plate", "xray"), ("raking-light", "raking_light"), ("macro", "macro")):
        got = run_js(js, {"case_id": "case_widows_supper", "kind": said, "focus": "", "region": ""})[0]["json"]
        assert got["ok"] and got["kind"] == want, (said, got)
    bad = run_js(js, {"case_id": "case_widows_supper", "kind": "infrared", "focus": "", "region": ""})[0]["json"]
    assert not bad["ok"] and "infrared" in bad["error"]
    evil = run_js(js, {"case_id": "../../etc", "kind": "uv", "focus": "", "region": ""})[0]["json"]
    assert not evil["ok"]


def test_parse_accepts_agent_object_and_rejects_junk():
    js = NODES["Restorer - Parse & Validate"]["parameters"]["jsCode"]
    req = {"Restorer - Validate & Guardrail": {"case_id": "case_widows_supper", "image_type": "xray"}}
    good = {"image_type": "xray", "simulated": True, "observations": ["A bright oval sits under the left figure."],
            "anomalies_detected": [], "confidence": 0.8, "refused": False, "refusal_reason": None}
    r = run_js(js, {"output": good}, req)[0]["json"]
    assert r["schema_valid"] and r["observations"] == good["observations"]
    r2 = run_js(js, {"output": json.dumps(good)}, req)[0]["json"]
    assert r2["schema_valid"]
    bad = run_js(js, {"output": "I think it is fine"}, req)[0]["json"]
    assert bad["schema_valid"] is False and bad["refused"] is True
    missing = run_js(js, {"output": {"image_type": "xray"}}, req)[0]["json"]
    assert missing["schema_valid"] is False


def test_guardrail_keeps_images_and_refuses_verdicts():
    js = NODES["Restorer - Validate & Guardrail"]["parameters"]["jsCode"]
    base = {"has_images": True, "session_id": "s1", "case_id": "case_widows_supper", "image_type": "xray", "region": None}
    ok = run_js(js, {**base, "question": "What is under the left figure?"})[0]
    assert ok["json"]["blocked"] is False and ok["json"]["session_id"] == "s1" and "binary" in ok
    no = run_js(js, {**base, "question": "Is this a forgery?"})[0]["json"]
    assert no["blocked"] is True and no["guard"] == "keyword_guard"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:  # report every failure, not just the first
            failed += 1
            print("FAIL", t.__name__, "-", repr(e)[:300])
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
