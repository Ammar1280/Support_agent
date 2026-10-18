"""Printing: the failures (input, expected, got), the score by case type, and run health."""

from collections import Counter, OrderedDict

from evals.graders import FAIL, PASS, SKIP, excerpt

TYPE_ORDER = ["lookup", "policy", "escalation", "no_fabrication", "stopping", "redteam"]


def type_sort_key(t):
    return (TYPE_ORDER.index(t), t) if t in TYPE_ORDER else (len(TYPE_ORDER), t)


def fmt_path(steps):
    if not steps:
        return "(no steps)"
    parts = []
    for s in steps:
        tool, args = s.get("tool"), s.get("args") or {}
        if tool in ("get_order", "check_policy"):
            parts.append(f"{tool}({next(iter(args.values()), '')})")
        elif tool == "draft_reply":
            parts.append(f"draft_reply(escalate={args.get('escalate')})")
        elif tool == "loop_guard":
            parts.append(f"loop_guard(suppressed {args.get('suppressed')})")
        else:
            parts.append(str(tool))
    return " -> ".join(parts)


def progress_line(row):
    c = row["case"]
    skipped = sum(1 for r in row["results"] if r["status"] == SKIP)
    note = f"  ({skipped} judge check(s) skipped)" if skipped else ""
    return f"  {row['status'].upper():<4}  {c['id']:<4} {c['type']:<15} scenario {c.get('scenario', '-'):<3}{note}"


def failure_block(row):
    c, run = row["case"], row["run"]
    msg = c["message"] if c["message"].strip() else "(empty message)"
    lines = [f"FAIL  {c['id']}  [{c['type']}]  scenario {c.get('scenario', '-')}",
             f"  input      {c['sender']}: \"{msg}\"",
             f"  path       {fmt_path(run.get('steps', []))}"]
    for r in row["results"]:
        if r["status"] == FAIL:
            lines += [f"  x {r['check']}",
                      f"      expected   {r['expected']}",
                      f"      got        {r['got']}"]
    rep = run.get("reply")
    if rep:
        lines.append(f"  reply      {excerpt(rep.get('message', ''), 300)}")
        if rep.get("handover_note"):
            lines.append(f"  handover   {excerpt(rep['handover_note'], 300)}")
    if c.get("observed"):
        lines.append(f"  week 4     {c['observed']}")
    return "\n".join(lines)


def score_table(rows):
    by = OrderedDict()
    for t in sorted({r["case"]["type"] for r in rows}, key=type_sort_key):
        sel = [r for r in rows if r["case"]["type"] == t]
        by[t] = (sum(1 for r in sel if r["status"] == PASS), len(sel))
    width = max([len(t) for t in by] + [5])
    out = ["SCORE BY CASE TYPE", f"  {'type':<{width}}  passed  total  score"]
    for t, (p, n) in by.items():
        out.append(f"  {t:<{width}}  {p:>6}  {n:>5}  {100 * p / n:>4.0f}%")
    p = sum(v[0] for v in by.values())
    n = sum(v[1] for v in by.values())
    out.append(f"  {'-' * (width + 24)}")
    out.append(f"  {'all':<{width}}  {p:>6}  {n:>5}  {100 * p / n:>4.0f}%"
               "   (read the rows above, not this line)")
    return "\n".join(out)


def health(rows):
    steps = [s for r in rows for s in r["run"].get("steps", [])]
    tools = Counter(s.get("tool") for s in steps)
    skipped = sum(1 for r in rows for x in r["results"] if x["status"] == SKIP)
    crashed = [r["case"]["id"] for r in rows if r["run"].get("crashed")]
    lines = ["RUN HEALTH (not scored)",
             f"  invalid_output steps : {tools.get('invalid_output', 0)}",
             f"  loop_guard steps     : {tools.get('loop_guard', 0)}",
             f"  cases that crashed   : {', '.join(crashed) if crashed else 'none'}",
             f"  judge checks skipped : {skipped}"]
    return "\n".join(lines)


def print_summary(rows, out):
    """Failures, score by type, run health. Progress lines are printed as cases finish."""
    p = lambda s="": print(s, file=out)
    failed = [r for r in rows if r["status"] == FAIL]
    p()
    if failed:
        p(f"FAILURES ({len(failed)} of {len(rows)})")
        p("=" * 72)
        for row in failed:
            p(failure_block(row))
            p()
    else:
        p("No failures.")
        p()
    p(score_table(rows))
    p()
    p(health(rows))
