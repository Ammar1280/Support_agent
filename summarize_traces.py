"""Turn a trace log into a readable per-scenario summary, so you can audit the PATH first.

  python summarize_traces.py before          -> prints and writes traces/summary_before.md
  python summarize_traces.py before after    -> also lists scenarios whose steps changed

The auto flags come from checks.py and are heuristics. Read the steps yourself before you
write a verdict in TRACE_REVIEW.md.
"""

import json
import sys
from collections import defaultdict


def load(label):
    steps = defaultdict(list)
    with open(f"traces/trace_{label}.jsonl", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            steps[e["scenario"]].append(e)
    with open(f"traces/replies_{label}.json", encoding="utf-8") as f:
        replies = {r["scenario"]: r for r in json.load(f)}
    return steps, replies


def fmt_step(e):
    a = e["args"]
    if e["tool"] in ("get_order", "check_policy"):
        arg = next(iter(a.values()), "")
    elif e["tool"] == "loop_guard":
        arg = f"suppressed {a.get('suppressed')}({next(iter(a.get('args', {}).values()), '')})"
    else:
        arg = ""
    return f"step {e['step']}: {e['tool']}({arg})"


def summary(label):
    steps, replies = load(label)
    out = [f"# Trace summary: {label}\n"]
    for sid in sorted(steps):
        r = replies.get(sid, {})
        flags = r.get("auto_flags", [])
        out.append(f"## Scenario {sid}  ({'FLAGGED' if flags else 'no auto flags'})")
        out.append(f"From {r.get('sender')}: {r.get('message')!r}\n")
        out.append("Steps: " + " -> ".join(fmt_step(e) for e in steps[sid]))
        total_ms = sum(e["ms"] for e in steps[sid])
        out.append(f"Total: {len(steps[sid])} steps, {total_ms:.0f} ms, cost {r.get('cost')}")
        for f_ in flags:
            out.append(f"- FLAG: {f_}")
        if r.get("reply"):
            out.append(f"Reply: {r['reply']['message']}")
            if r["reply"]["handover_note"]:
                out.append(f"Handover: {r['reply']['handover_note']}")
        out.append("")
    return "\n".join(out), steps


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    labels = sys.argv[1:] or ["before"]
    sums = {}
    for label in labels:
        text, steps = summary(label)
        sums[label] = steps
        with open(f"traces/summary_{label}.md", "w", encoding="utf-8") as f:
            f.write(text)
        print(text)
    if len(labels) == 2:
        b, a = sums[labels[0]], sums[labels[1]]
        print(f"# Changes {labels[0]} -> {labels[1]}")
        for sid in sorted(b):
            if sid in a and [e["tool"] for e in b[sid]] != [e["tool"] for e in a[sid]]:
                print(f"Scenario {sid}: {len(b[sid])} steps -> {len(a[sid])} steps")
                print("  before: " + " -> ".join(fmt_step(e) for e in b[sid]))
                print("  after:  " + " -> ".join(fmt_step(e) for e in a[sid]))


if __name__ == "__main__":
    main()
