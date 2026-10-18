"""Reproduces the repeated-call failure mode (scenario 18) without any API key.

A scripted "model" does exactly what scenario 18 asks: three identical get_order(A-91)
calls, then a reply. The test then asserts what the pack expects: exactly ONE get_order.

  python -m unittest -v test_repeat_call

Red -> green:
  * With DEDUPE_REPEATED_CALLS = False in agent.py, test_default_loop_issues_one_get_order
    FAILS (the loop executes get_order three times).
  * Flip the switch to True and it PASSES.
"""

import unittest

import agent
from llm import ScriptedLLM

GET = {"tool": "get_order", "args": {"order_id": "A-91"}}
REPLY = {"tool": "draft_reply", "args": {
    "message": "Order A-91 was delivered on 1 Sep 2026.", "escalate": False,
    "handover_note": None}}
SENDER, MESSAGE = "Omar Rashid", "Check A-91, then check A-91 again, then once more, I want to be sure."


def run(dedupe=None):
    tracer = agent.Tracer()           # in memory: never touches traces/
    result = agent.run_agent(SENDER, MESSAGE, ScriptedLLM([GET, GET, GET, REPLY]),
                             tracer, scenario=18, dedupe=dedupe)
    return tracer.run, result


class RepeatedCall(unittest.TestCase):
    def test_default_loop_issues_one_get_order(self):
        """Uses whatever DEDUPE_REPEATED_CALLS is set to in agent.py (the real config)."""
        entries, result = run()
        calls = [e for e in entries if e["tool"] == "get_order"]
        self.assertEqual(len(calls), 1, f"get_order issued {len(calls)} times, expected 1")
        self.assertTrue(result["ended_cleanly"])

    def test_guard_logs_suppressed_calls_as_loop_guard(self):
        entries, result = run(dedupe=True)
        tools = [e["tool"] for e in entries]
        self.assertEqual(tools, ["get_order", "loop_guard", "loop_guard", "draft_reply"])
        self.assertTrue(result["ended_cleanly"])
        self.assertEqual(entries[1]["args"]["suppressed"], "get_order")

    def test_without_guard_the_failure_is_visible(self):
        entries, _ = run(dedupe=False)
        self.assertEqual([e["tool"] for e in entries].count("get_order"), 3)


if __name__ == "__main__":
    unittest.main()
