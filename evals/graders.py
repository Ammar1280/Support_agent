"""Programmatic graders. Anything code can decide is decided here, with no model involved.

A "run" is the evidence for one case:
    {"steps": [trace entries], "reply": {"message", "escalate", "handover_note"} or None,
     "ended_cleanly": bool, "crashed": str (only if the agent raised)}

Each grader returns a result dict: {"check", "status", "expected", "got"} where status is
"pass", "fail" or "skip". "expected" and "got" are plain text, so a failure prints without
any further work.

Text is normalised before matching (case, unicode dashes and quotes, "POL 114" -> "pol-114"),
because real replies from the agent use non-breaking hyphens ("POL-114").
"""

import re
import unicodedata
from collections import Counter

from evals import judge as judge_mod

PASS, FAIL, SKIP = "pass", "fail", "skip"
TOOL_CALLS = ("get_order", "check_policy")
FIELD_NAMES = {"both": "reply or handover note", "message": "message", "handover": "handover note"}
PLACEHOLDER = re.compile(r"\[[^\]]*(insert|placeholder|todo|tbd)[^\]]*\]", re.I)

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'}


def norm(text):
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = t.translate(_DASHES).translate(_QUOTES).lower()
    t = re.sub(r"pol[\s-]*(\d{3})", r"pol-\1", t)
    return re.sub(r"\s+", " ", t).strip()


def result(check, status, expected="", got=""):
    return {"check": check, "status": status, "expected": expected, "got": got}


def reply_text(run, field="both"):
    r = run.get("reply")
    if not r:
        return ""
    msg, note = r.get("message") or "", r.get("handover_note") or ""
    if field == "message":
        return msg
    if field == "handover":
        return note
    return msg + "\n" + note


def executed_calls(run):
    """[(step, tool, argument)] for tool calls that were really executed.
    A call suppressed by the loop guard is logged as `loop_guard`, so it is not here."""
    out = []
    for s in run.get("steps", []):
        if s.get("tool") in TOOL_CALLS:
            val = next(iter((s.get("args") or {}).values()), "")
            out.append((s.get("step"), s["tool"], str(val).strip().upper()))
    return out


def fmt_calls(pairs):
    return ", ".join(f"{t}({a})" for t, a in pairs) or "(no tool calls)"


def excerpt(text, n=200):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 3] + "..."


# ------------------------------------------------------------------ global checks -----
def global_checks(run):
    """Applied to every case: the stopping and fabrication rules from section 5 of the pack."""
    steps = run.get("steps", [])
    drafts = [s for s in steps if s.get("tool") == "draft_reply"]
    last = steps[-1].get("tool") if steps else "none"
    ok = bool(run.get("ended_cleanly")) and len(drafts) == 1 and last == "draft_reply"
    out = [result(
        "ends_cleanly", PASS if ok else FAIL,
        "exactly one draft_reply, and it is the last step",
        f"{len(drafts)} draft_reply step(s); last step is {last}; "
        f"ended_cleanly={run.get('ended_cleanly')}")]

    text = reply_text(run)
    m = PLACEHOLDER.search(text)
    out.append(result("no_placeholder_text", FAIL if m else PASS,
                      "no unfilled placeholder such as [Insert ...]",
                      f"found {m.group(0)!r}" if m else "none"))

    counts = Counter((t, a) for _, t, a in executed_calls(run))
    repeats = {k: v for k, v in counts.items() if v > 1}
    out.append(result(
        "no_repeated_calls", FAIL if repeats else PASS,
        "no identical tool call executed twice",
        "; ".join(f"{t}({a}) executed {n} times" for (t, a), n in repeats.items()) or "none"))
    return out


# ------------------------------------------------------------------ case checks -------
def c_calls(spec, run):
    want = [(t, a.upper()) for t, a in spec["expect"]]
    have = [(t, a) for _, t, a in executed_calls(run)]
    ok = Counter(want) == Counter(have)
    note = "  (any order)" if len(want) > 1 else ""
    return result("calls", PASS if ok else FAIL, fmt_calls(want) + note, fmt_calls(have))


def c_escalate(spec, run):
    r = run.get("reply")
    want = bool(spec["expect"])
    if not r:
        return result("escalate", FAIL, f"escalate={want}", "no reply was produced")
    got = bool(r.get("escalate"))
    return result("escalate", PASS if got == want else FAIL, f"escalate={want}", f"escalate={got}")


def c_cites(spec, run):
    text = norm(reply_text(run, spec.get("field", "both")))
    missing = [p for p in spec["expect"] if norm(p) not in text]
    where = FIELD_NAMES[spec.get("field", "both")]
    return result("cites", FAIL if missing else PASS, "cites " + ", ".join(spec["expect"]),
                  ("missing from the " + where + ": " + ", ".join(missing)) if missing
                  else "all cited")


def c_contains(spec, run):
    field = spec.get("field", "both")
    text = norm(reply_text(run, field))
    missing = [g for g in spec["expect"] if not any(norm(a) in text for a in g)]
    exp = "; ".join(("one of " + str(g)) if len(g) > 1 else repr(g[0]) for g in spec["expect"])
    return result(
        "contains", FAIL if missing else PASS, f"{FIELD_NAMES[field]} contains {exp}",
        ("missing " + "; ".join(("one of " + str(g)) if len(g) > 1 else repr(g[0])
                                for g in missing)) if missing else "all present")


def c_not_contains(spec, run):
    field = spec.get("field", "both")
    text = norm(reply_text(run, field))
    found = [w for w in spec["expect"] if norm(w) in text]
    return result("not_contains", FAIL if found else PASS,
                  f"{FIELD_NAMES[field]} contains none of {spec['expect']}",
                  ("found " + ", ".join(repr(w) for w in found)) if found else "none found")


def c_steps_at_most(spec, run):
    n = len(run.get("steps", []))
    return result("steps_at_most", PASS if n <= spec["expect"] else FAIL,
                  f"at most {spec['expect']} step(s)", f"{n} step(s)")


CHECKS = {
    "calls": c_calls,
    "escalate": c_escalate,
    "cites": c_cites,
    "contains": c_contains,
    "not_contains": c_not_contains,
    "steps_at_most": c_steps_at_most,
}


def c_judge(spec, run, judge):
    """The only model-graded check. One narrow YES/NO question (see judge.py)."""
    qid, want = spec["question"], spec["expect"]
    name = f"judge:{qid}"
    exp = f"{want}  <- {judge_mod.QUESTIONS[qid]}"
    if judge is None:
        return result(name, SKIP, exp, "no judge model available (skipped)")
    text = reply_text(run, spec.get("field", "message"))
    if not text.strip():
        return result(name, FAIL, exp, "no reply text to judge")
    try:
        ans = judge.ask(qid, text)
    except judge_mod.JudgeError as e:
        return result(name, FAIL, exp, f"judge error: {e}")
    return result(name, PASS if ans == want else FAIL, exp, ans)


def grade_case(case, run, judge=None):
    if run.get("crashed"):
        return [result("agent_ran", FAIL, "the agent runs to completion", run["crashed"])]
    results = global_checks(run)
    for spec in case["checks"]:
        if spec["kind"] == "judge":
            results.append(c_judge(spec, run, judge))
        else:
            results.append(CHECKS[spec["kind"]](spec, run))
    return results


def case_status(results):
    return FAIL if any(r["status"] == FAIL for r in results) else PASS
