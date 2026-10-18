"""Run the eval suite: ONE command, prints a score by case type and every failure.

  python run_evals.py                      run every case against the agent (needs your API key)
  python run_evals.py --replay before      grade the committed traces/trace_before.jsonl instead
                                           (no agent calls; the judge is skipped without a key)
  python run_evals.py --type redteam       only one case type
  python run_evals.py --only E03,E12       only some cases
  python run_evals.py --no-judge           programmatic checks only

Cases live in evals/cases.json and evals/redteam_fixtures.json. Exit code is 0 when every
case passes and 1 otherwise, so it can run in CI.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from evals import graders, report            # noqa: E402
from evals.judge import Judge                # noqa: E402

CASE_FILES = ("evals/cases.json", "evals/redteam_fixtures.json")


def load_cases():
    cases = []
    for name in CASE_FILES:
        with open(ROOT / name, encoding="utf-8") as f:
            cases += json.load(f)
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"Duplicate case ids: {sorted(dupes)}")
    return cases


def load_replay(label):
    trace = ROOT / "traces" / f"trace_{label}.jsonl"
    replies = ROOT / "traces" / f"replies_{label}.json"
    if not trace.exists() or not replies.exists():
        raise SystemExit(f"Need {trace} and {replies}. Run run_scenarios.py --label {label} first.")
    steps = defaultdict(list)
    with open(trace, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                steps[e["scenario"]].append(e)
    with open(replies, encoding="utf-8") as f:
        by_scenario = {r["scenario"]: r for r in json.load(f)}

    def get(case):
        sid = case["scenario"]
        r = by_scenario.get(sid)
        if not steps.get(sid) or r is None:
            return {"steps": [], "reply": None, "ended_cleanly": False,
                    "crashed": f"no trace for scenario {sid} in label {label!r}"}
        return {"steps": steps[sid], "reply": r.get("reply"),
                "ended_cleanly": bool(r.get("ended_cleanly"))}
    return get


def live_runner(llm):
    import agent

    def get(case):
        tracer = agent.Tracer(None)
        try:
            res = agent.run_agent(case["sender"], case["message"], llm, tracer,
                                  scenario=case.get("scenario", 0))
        except Exception as e:                       # a crash is a failed case, not a dead run
            return {"steps": list(tracer.run), "reply": None, "ended_cleanly": False,
                    "crashed": f"{type(e).__name__}: {e}"}
        return {"steps": list(tracer.run), "reply": res["reply"],
                "ended_cleanly": res["ended_cleanly"]}
    return get


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from llm import load_env, make_llm
    load_env(str(ROOT / ".env"))

    ap = argparse.ArgumentParser(description="Eval suite for the Merik support agent.")
    ap.add_argument("--replay", metavar="LABEL", help="grade traces/trace_LABEL.jsonl, no agent calls")
    ap.add_argument("--provider", default=os.getenv("PROVIDER", "gemini"),
                    choices=["gemini", "anthropic", "groq"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--type", default="", help="only this case type")
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--no-judge", action="store_true", help="skip the model-graded checks")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to wait between cases")
    ap.add_argument("--json-out", default="evals/results/last_run.json")
    a = ap.parse_args(argv)

    cases = load_cases()
    if a.type:
        cases = [c for c in cases if c["type"] == a.type]
    if a.only:
        want = {x.strip() for x in a.only.split(",")}
        cases = [c for c in cases if c["id"] in want]
    if not cases:
        raise SystemExit("No cases selected.")

    llm = None
    not_replayable = 0
    if a.replay:
        # cases found by probing (scenario 0) have no audited trace; they need a live run
        not_replayable = sum(1 for c in cases if not c.get("scenario"))
        cases = [c for c in cases if c.get("scenario")]
        if not cases:
            raise SystemExit("No replayable cases selected.")
        get_run = load_replay(a.replay)
        mode = f"replay of traces/trace_{a.replay}.jsonl (agent not called)"
        if not_replayable:
            mode += f"; {not_replayable} probe-found case(s) skipped, they need a live run"
    else:
        llm = make_llm(a.provider, a.model)
        get_run = live_runner(llm)
        import agent
        mode = (f"live run, provider={a.provider}, "
                f"DEDUPE_REPEATED_CALLS={agent.DEDUPE_REPEATED_CALLS}, "
                f"REJECT_PLACEHOLDER_DRAFTS={getattr(agent, 'REJECT_PLACEHOLDER_DRAFTS', 'n/a')}")

    judge, judge_note = None, "judge off (--no-judge)"
    if not a.no_judge:
        try:
            judge = Judge(llm or make_llm(a.provider, a.model))
            judge_note = f"judge on ({a.provider})"
        except Exception as e:                         # no key in replay mode, SDK missing, ...
            judge_note = f"judge unavailable, model-graded checks skipped ({type(e).__name__})"

    header = f"Merik agent evals: {len(cases)} cases | {mode} | {judge_note}"
    rows = []
    print(header, flush=True)
    for i, case in enumerate(cases):
        if i and a.delay and not a.replay:
            import time
            time.sleep(a.delay)
        run = get_run(case)
        results = graders.grade_case(case, run, judge)
        row = {"case": case, "run": run, "results": results,
               "status": graders.case_status(results)}
        rows.append(row)
        print(report.progress_line(row), flush=True)

    report.print_summary(rows, sys.stdout)

    out_path = ROOT / a.json_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([{"id": r["case"]["id"], "type": r["case"]["type"], "status": r["status"],
                    "results": r["results"], "steps": r["run"].get("steps", []),
                    "reply": r["run"].get("reply")} for r in rows],
                  f, indent=2, ensure_ascii=False)
    return 0 if all(r["status"] == graders.PASS for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
