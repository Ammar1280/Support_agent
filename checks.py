"""Automatic path and reply checks for one scenario run.

These are a first pass to point you at the steps worth reading. They are heuristics:
the verdicts in TRACE_REVIEW.md are yours, made by reading the trace.
"""

import json
from collections import Counter

TOOL_CALLS = ("get_order", "check_policy")


def _key(tool, args):
    return (tool, json.dumps(args, sort_keys=True))


def evaluate(expect, entries, result):
    """Return a list of human-readable failures (empty list = no flags)."""
    fails = []

    # --- path -------------------------------------------------------------------------
    drafts = [e for e in entries if e["tool"] == "draft_reply"]
    if not result["ended_cleanly"] or len(drafts) != 1 or entries[-1]["tool"] != "draft_reply":
        fails.append("run did not end cleanly with exactly one draft_reply")

    got = [(e["step"], _key(e["tool"], e["args"])) for e in entries if e["tool"] in TOOL_CALLS]
    want = Counter(_key(t, a) for t, a in expect.get("calls", []))
    have = Counter(k for _, k in got)

    for k, n in (have - want).items():
        steps = [s for s, kk in got if kk == k]
        fails.append(f"unexpected/extra call {k[0]}{k[1]} x{n} (steps {steps})")
    for k, n in (want - have).items():
        fails.append(f"missing call {k[0]}{k[1]} x{n}")

    # --- reply ------------------------------------------------------------------------
    reply = result.get("reply")
    if reply:
        text = (reply["message"] + " " + (reply["handover_note"] or "")).lower()
        if reply["escalate"] != expect.get("escalate", False):
            fails.append(f"escalate={reply['escalate']}, expected {expect.get('escalate', False)}")
        for pid in expect.get("cites", []):
            if pid.lower() not in text:
                fails.append(f"does not cite {pid}")
        for group in expect.get("must_contain_any", []):
            if not any(g.lower() in text for g in group):
                fails.append(f"missing one of {group}")
        for bad in expect.get("must_not_contain", []):
            if bad.lower() in text:
                fails.append(f"contains forbidden text {bad!r}")
    return fails
