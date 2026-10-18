"""Tests for the eval suite itself (no API key needed):  python -m unittest -v test_evals

An eval suite that is wrong is worse than none, so these pin down the graders: they must
pass good runs, fail bad ones, and every case must be satisfiable.
"""

import json
import unittest
from pathlib import Path

from evals import graders
from evals.graders import FAIL, PASS, SKIP
from evals.judge import Judge, JudgeError, QUESTIONS, parse_answer
from llm import LLMOutput

ROOT = Path(__file__).resolve().parent


def load_cases():
    cases = []
    for name in ("evals/cases.json", "evals/redteam_fixtures.json"):
        cases += json.loads((ROOT / name).read_text(encoding="utf-8"))
    return cases


def step(n, tool, arg=None, **args):
    a = {"order_id": arg} if tool == "get_order" else {"policy_id": arg} if tool == "check_policy" else args
    return {"step": n, "tool": tool, "args": a}


def run_of(calls, message, escalate=False, handover=None):
    steps = [step(i + 1, t, a) for i, (t, a) in enumerate(calls)]
    steps.append(step(len(steps) + 1, "draft_reply", escalate=escalate))
    return {"steps": steps, "ended_cleanly": True,
            "reply": {"message": message, "escalate": escalate, "handover_note": handover}}


def golden_run(case):
    """Build a run that satisfies every programmatic check of a case, from the case itself."""
    calls, esc, msg, note = [], False, [], []
    for spec in case["checks"]:
        k = spec["kind"]
        if k == "calls":
            calls = [tuple(x) for x in spec["expect"]]
        elif k == "escalate":
            esc = spec["expect"]
        elif k == "cites":
            msg += spec["expect"]
        elif k == "contains":
            target = note if spec.get("field") == "handover" else msg
            target += [g[0] for g in spec["expect"]]
    return run_of(calls, " ".join(msg + note), esc, " ".join(note + msg) if esc else None)


class Normalisation(unittest.TestCase):
    def test_non_breaking_hyphen_still_cites_the_policy(self):
        # Real reply from the audited run, scenario 2: "POL‑114" (U+2011).
        run = run_of([("get_order", "A-91")], "see our damaged‑on‑arrival policy (POL‑114)")
        r = graders.c_cites({"expect": ["POL-114"]}, run)
        self.assertEqual(r["status"], PASS)

    def test_en_dash_range_matches(self):
        run = run_of([], "Refunds take 5–10 working days.")
        r = graders.c_contains({"expect": [["5 to 10", "5-10"]]}, run)
        self.assertEqual(r["status"], PASS)


class Checks(unittest.TestCase):
    def test_missing_call_fails(self):
        run = run_of([("get_order", "A-91")], "hi")
        spec = {"expect": [["get_order", "A-91"], ["check_policy", "POL-114"]]}
        self.assertEqual(graders.c_calls(spec, run)["status"], FAIL)

    def test_call_order_does_not_matter_but_counts_do(self):
        run = run_of([("check_policy", "POL-101"), ("get_order", "A-11")], "hi")
        ok = {"expect": [["get_order", "A-11"], ["check_policy", "POL-101"]]}
        self.assertEqual(graders.c_calls(ok, run)["status"], PASS)
        extra = run_of([("get_order", "A-11"), ("get_order", "A-11")], "hi")
        self.assertEqual(graders.c_calls({"expect": [["get_order", "A-11"]]}, extra)["status"], FAIL)

    def test_repeated_calls_fail_the_global_check(self):
        run = run_of([("get_order", "A-91")] * 3, "delivered 1 Sep")
        res = {r["check"]: r for r in graders.global_checks(run)}
        self.assertEqual(res["no_repeated_calls"]["status"], FAIL)

    def test_loop_guard_step_is_not_a_repeat(self):
        run = run_of([("get_order", "A-91")], "delivered 1 Sep")
        run["steps"].insert(1, {"step": 2, "tool": "loop_guard", "args": {"suppressed": "get_order"}})
        res = {r["check"]: r for r in graders.global_checks(run)}
        self.assertEqual(res["no_repeated_calls"]["status"], PASS)

    def test_placeholder_text_fails(self):
        # Real reply from the audited run, scenario 18.
        run = run_of([], "Status: [Insert status from system]")
        res = {r["check"]: r for r in graders.global_checks(run)}
        self.assertEqual(res["no_placeholder_text"]["status"], FAIL)

    def test_no_draft_reply_fails_ends_cleanly(self):
        run = {"steps": [step(1, "get_order", "A-91")], "reply": None, "ended_cleanly": False}
        res = {r["check"]: r for r in graders.global_checks(run)}
        self.assertEqual(res["ends_cleanly"]["status"], FAIL)

    def test_crash_is_a_failed_case(self):
        out = graders.grade_case({"checks": []}, {"steps": [], "crashed": "RateLimitError: 429"})
        self.assertEqual(graders.case_status(out), FAIL)

    def test_forbidden_text_fails(self):
        run = run_of([("get_order", "A-91")], "Your order was delivered on 1 Sep")
        self.assertEqual(graders.c_not_contains({"expect": ["delivered"]}, run)["status"], FAIL)


class JudgeBox(unittest.TestCase):
    class Fake:
        def __init__(self, *texts):
            self.texts = list(texts)
            self.calls = 0

        def complete(self, system, messages):
            self.calls += 1
            return LLMOutput(self.texts.pop(0) if self.texts else "")

    def test_only_yes_or_no_are_accepted(self):
        self.assertEqual(parse_answer('{"answer": "yes"}'), "YES")
        self.assertEqual(parse_answer('```json\n{"answer": "NO"}\n```'), "NO")
        self.assertIsNone(parse_answer('{"answer": "maybe"}'))
        self.assertIsNone(parse_answer("YES"))
        self.assertIsNone(parse_answer(""))

    def test_bad_answer_is_retried_once_then_errors(self):
        fake = self.Fake("hmm", "still not json")
        with self.assertRaises(JudgeError):
            Judge(fake).ask("promises_outcome", "text")
        self.assertEqual(fake.calls, 2)

    def test_judge_check_passes_fails_and_skips(self):
        run = run_of([], "A colleague will review this.")
        spec = {"kind": "judge", "question": "promises_outcome", "expect": "NO"}
        self.assertEqual(graders.c_judge(spec, run, Judge(self.Fake('{"answer": "NO"}')))["status"], PASS)
        self.assertEqual(graders.c_judge(spec, run, Judge(self.Fake('{"answer": "YES"}')))["status"], FAIL)
        self.assertEqual(graders.c_judge(spec, run, None)["status"], SKIP)

    def test_judge_error_fails_instead_of_passing_silently(self):
        run = run_of([], "hello")
        spec = {"kind": "judge", "question": "promises_outcome", "expect": "NO"}
        self.assertEqual(graders.c_judge(spec, run, Judge(self.Fake("x", "y")))["status"], FAIL)


class CaseFiles(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases()

    def test_at_least_twenty_unique_cases(self):
        ids = [c["id"] for c in self.cases]
        self.assertGreaterEqual(len(ids), 20)
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_case_is_traceable_to_real_behaviour(self):
        for c in self.cases:
            for key in ("id", "type", "scenario", "sender", "message", "origin", "observed", "checks"):
                self.assertIn(key, c, f"{c.get('id')} is missing {key}")
            self.assertTrue(c["origin"].strip(), f"{c['id']} has an empty origin")
            if c["scenario"] >= 1:       # cases from the audited run must point at its trace
                self.assertIn("trace_before.jsonl", c["origin"])
            self.assertTrue(c["checks"])

    def test_redteam_fixtures_are_all_typed_redteam(self):
        red = json.loads((ROOT / "evals/redteam_fixtures.json").read_text(encoding="utf-8"))
        self.assertTrue(red)
        self.assertTrue(all(c["type"] == "redteam" for c in red))

    def test_programmatic_checks_outnumber_judge_checks(self):
        kinds = [s["kind"] for c in self.cases for s in c["checks"]]
        self.assertGreater(kinds.count("calls"), 0)
        self.assertGreater(len(kinds) - kinds.count("judge"), 3 * kinds.count("judge"))

    def test_judge_questions_exist(self):
        for c in self.cases:
            for s in c["checks"]:
                if s["kind"] == "judge":
                    self.assertIn(s["question"], QUESTIONS)
                    self.assertIn(s["expect"], ("YES", "NO"))

    def test_every_case_can_pass(self):
        """A case whose checks contradict each other would fail forever."""
        for c in self.cases:
            results = graders.grade_case(c, golden_run(c), judge=None)
            bad = [r for r in results if r["status"] == FAIL]
            self.assertEqual(bad, [], f"{c['id']} cannot pass: {bad}")

    def test_a_blank_run_fails_every_case_with_a_lookup_or_escalation(self):
        blank = run_of([], "Hello")
        for c in self.cases:
            kinds = {s["kind"] for s in c["checks"]}
            if "calls" in kinds and any(s["kind"] == "calls" and s["expect"] for s in c["checks"]):
                self.assertEqual(graders.case_status(graders.grade_case(c, blank)), FAIL, c["id"])


if __name__ == "__main__":
    unittest.main()
