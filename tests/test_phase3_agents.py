"""
Phase 3 Multi-Cloud AI Router & 8-Agent Council Verification Suite
==================================================================
1. Deterministic unit tests: JSON extractor edge cases & HTTP 429/503 circuit-breaker failover.
2. Live 4-Cloud Gateway checks: Google AI Studio, Groq LPU, OpenRouter, and Kilo AI Gateway.
3. Live End-to-End Agent workflows: SEC Filing RAG Audit, 8-Agent Stock Debate, Morning Briefing.
"""

import io
import sys
import time
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.agents import (
    audit_filing,
    clear_cooldowns,
    debate_stock,
    extract_key_filing_snippets,
    llm_router,
    morning_briefing,
)
from backend.agents.llm_router import _extract_json_object, _is_on_cooldown


def run_router_unit_tests() -> None:
    print("=== PART 1: AI ROUTER FAILOVER & JSON UNIT TESTS ===")

    # 1. JSON extractor handles raw JSON, fenced code blocks, and preamble/postamble text
    raw = '{"action": "BUY", "confidence_pct": 78}'
    fenced = 'Here is my analysis:\n```json\n{"action": "HOLD", "confidence_pct": 55}\n```\nDone.'
    noisy = 'Thinking carefully... {"action": "SELL", "confidence_pct": 64} Thanks!'
    assert _extract_json_object(raw)["action"] == "BUY"
    assert _extract_json_object(fenced)["action"] == "HOLD"
    assert _extract_json_object(noisy)["action"] == "SELL"
    print("[PASS] JSON extractor handles raw, fenced markdown, and preamble text")

    # 2. Automatic circuit-breaker failover on HTTP 429 & HTTP 503
    clear_cooldowns()
    try:
        test_chain = [
            ("mock_primary", "model-a"),
            ("mock_secondary", "model-b"),
            ("mock_backup", "model-c"),
        ]

        def fake_dispatch(provider, model, sys_p, usr_p, max_tok, temp, expect_json=False):
            if provider == "mock_primary":
                raise urllib.error.HTTPError(
                    "https://example.test", 429, "Too Many Requests", {}, io.BytesIO(b"rate limit")
                )
            if provider == "mock_secondary":
                raise urllib.error.HTTPError(
                    "https://example.test", 503, "Service Unavailable", {}, io.BytesIO(b"overloaded")
                )
            return '{"action": "BUY", "confidence_pct": 81}'

        with patch("backend.agents.llm_router._dispatch_provider", side_effect=fake_dispatch):
            res1 = llm_router.generate(
                role="judge",
                system_prompt="Return JSON",
                user_prompt="Test",
                expect_json=True,
                chain_override=test_chain,
            )
            assert res1["provider_used"] == "mock_backup"
            assert res1["model_used"] == "model-c"
            assert res1["json"]["action"] == "BUY"
            assert len(res1["attempts"]) == 2
            assert _is_on_cooldown("mock_primary", "model-a") is not None
            assert _is_on_cooldown("mock_secondary", "model-b") is not None

            # Second call should immediately skip cooled-down gateways without invoking them
            called_targets = []

            def track_dispatch(provider, model, sys_p, usr_p, max_tok, temp, expect_json=False):
                called_targets.append((provider, model))
                return "ok"

            with patch("backend.agents.llm_router._dispatch_provider", side_effect=track_dispatch):
                res2 = llm_router.generate(
                    role="judge",
                    system_prompt="Test",
                    user_prompt="Test",
                    chain_override=test_chain,
                )
                assert res2["provider_used"] == "mock_backup"
                assert called_targets == [("mock_backup", "model-c")]
                assert all("skipped" in att for att in res2["attempts"])

        print("[PASS] Multi-Cloud HTTP 429/503 automatic failover & SQLite cooldown circuit breaker")
    finally:
        clear_cooldowns()


def run_live_agent_tests() -> int:
    clear_cooldowns()
    failures = []

    def check(name, fn):
        t0 = time.time()
        try:
            res = fn()
            dt = round(time.time() - t0, 2)
            assert res and (not isinstance(res, dict) or "error" not in res), f"Error in {name}: {res}"
            print(f"[PASS] {name} ({dt}s)")
            return res
        except Exception as exc:
            dt = round(time.time() - t0, 2)
            print(f"[FAIL] {name} ({dt}s): {exc}")
            failures.append((name, str(exc)))
            return None

    print("\n=== PART 2: LIVE 4-CLOUD GATEWAY SWITCHER TESTS ===")
    health = check("Gateway Health Check", lambda: llm_router.gateway_health())
    if health:
        print(f"       -> Gateways={health['gateways']}")

    ping_sys = "Reply in one short plain-English sentence only."
    ping_usr = "Confirm you are online for DoomsBlerg Terminal."

    g_res = check(
        "Google AI Studio Live Inference",
        lambda: llm_router.generate(
            role="macro",
            system_prompt=ping_sys,
            user_prompt=ping_usr,
            max_tokens=150,
            chain_override=[("google", "gemini-2.5-flash"), ("google", "gemini-3.5-flash")],
        ),
    )
    if g_res:
        print(f"       -> {g_res['provider_used']}:{g_res['model_used']} ({g_res['latency_ms']}ms): {g_res['text'][:90]}")

    q_res = check(
        "Groq LPU Live Inference",
        lambda: llm_router.generate(
            role="sentiment",
            system_prompt=ping_sys,
            user_prompt=ping_usr,
            max_tokens=450,
            chain_override=[("groq", "qwen/qwen3.8-27b"), ("groq", "openai/gpt-oss-120b")],
        ),
    )
    if q_res:
        print(f"       -> {q_res['provider_used']}:{q_res['model_used']} ({q_res['latency_ms']}ms): {q_res['text'][:90]}")

    or_res = check(
        "OpenRouter Free Pool Live Inference",
        lambda: llm_router.generate(
            role="bull",
            system_prompt=ping_sys,
            user_prompt=ping_usr,
            max_tokens=300,
            chain_override=[
                ("openrouter", "nvidia/nemotron-3.5-lightning:free"),
                ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
            ],
        ),
    )
    if or_res:
        print(f"       -> {or_res['provider_used']}:{or_res['model_used']} ({or_res['latency_ms']}ms): {or_res['text'][:90]}")

    k_res = check(
        "Kilo AI Gateway Live Inference (Zero-Key Anonymous)",
        lambda: llm_router.generate(
            role="bear",
            system_prompt=ping_sys,
            user_prompt=ping_usr,
            max_tokens=300,
            chain_override=[("kilo", "reflection/beam-free")],
        ),
    )
    if k_res:
        print(f"       -> {k_res['provider_used']}:{k_res['model_used']} ({k_res['latency_ms']}ms): {k_res['text'][:90]}")

    print("\n=== PART 3: LIVE END-TO-END AI AGENT TESTS ===")
    snippets = check("SEC Filing RAG Snippet Extractor (AAPL)", lambda: extract_key_filing_snippets("AAPL"))
    if snippets:
        assert snippets.get("snippets_extracted", 0) > 0, "Expected at least 1 risk snippet"
        print(f"       -> Extracted {snippets['snippets_extracted']} snippets from {snippets['form']} ({snippets['filing_date']})")

    audit = check("Fundamental AI SEC Auditor (AAPL)", lambda: audit_filing("AAPL"))
    if audit:
        a_obj = audit.get("audit") or {}
        assert "plain_english_summary" in a_obj or "red_flags" in a_obj, f"Unexpected audit payload: {a_obj}"
        print(f"       -> Auditor={audit['provider_used']} | Risk={a_obj.get('overall_risk_level')} | Flags={len(a_obj.get('red_flags', []))}")

    debate = check("8-Agent Buy/Sell Council Debate (AAPL)", lambda: debate_stock("AAPL"))
    if debate:
        verdict = debate.get("verdict") or {}
        agents = debate.get("agents") or {}
        expected_agents = {
            "1_quant_and_technicals_python",
            "2_geospatial_scout_python",
            "3_fundamental_auditor",
            "4_macro_economist",
            "5_sentiment_scout",
            "6_bull_advocate",
            "7_bear_advocate",
            "8_risk_officer_judge",
        }
        assert expected_agents.issubset(agents.keys()), f"Missing agents: {expected_agents - set(agents.keys())}"
        assert verdict.get("computed_entry_price") is not None
        assert verdict.get("computed_stop_loss") is not None
        assert verdict.get("quant_score_100") is not None
        assert verdict.get("action") in {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"} or verdict.get("plain_english_verdict")
        print(
            f"       -> Verdict={verdict.get('action')} ({verdict.get('confidence_pct')}% conf) | "
            f"Entry=${verdict.get('computed_entry_price')} | Stop=${verdict.get('computed_stop_loss')} | "
            f"Judge={agents['8_risk_officer_judge']['provider']}"
        )

    brief = check("Morning Command Center Briefing", lambda: morning_briefing())
    if brief:
        assert len(brief.get("briefing", "")) > 40, "Briefing unexpectedly short"
        print(f"       -> Anchor={brief['provider_used']} | Words={len(brief['briefing'].split())}")

    print("\n=== PHASE 3 SUMMARY ===")
    print(f"Failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    run_router_unit_tests()
    raise SystemExit(run_live_agent_tests())
