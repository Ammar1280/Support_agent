"""Run the 20 scenarios through the agent and write the traces.

  python run_scenarios.py --provider gemini --label before
  python run_scenarios.py --provider gemini --label after
  python run_scenarios.py --provider anthropic --label before --only 18

Writes traces/trace_<label>.jsonl (one line per step) and traces/replies_<label>.json
(full replies plus the automatic flags). It uses the DEDUPE_REPEATED_CALLS switch in
agent.py unless you force it with --dedupe or --no-dedupe.
"""

import argparse
import json
import os
import sys

import agent
import checks
from llm import load_env, make_llm


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_env()

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.getenv("PROVIDER", "gemini"),
                    choices=["gemini", "anthropic","groq"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--label", default="before", help="before | after | anything")
    ap.add_argument("--only", default="", help="comma-separated scenario ids, e.g. 18,20")
    ap.add_argument("--scenarios", default="scenarios.json")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dedupe", dest="dedupe", action="store_true", default=None)
    g.add_argument("--no-dedupe", dest="dedupe", action="store_false")
    a = ap.parse_args(argv)

    with open(a.scenarios, encoding="utf-8") as f:
        scenarios = json.load(f)
    if a.only:
        wanted = {int(x) for x in a.only.split(",")}
        scenarios = [s for s in scenarios if s["id"] in wanted]

    os.makedirs("traces", exist_ok=True)
    trace_path = os.path.join("traces", f"trace_{a.label}.jsonl")
    replies_path = os.path.join("traces", f"replies_{a.label}.json")
    if not a.only:                       # a full run starts from a clean file
        open(trace_path, "w", encoding="utf-8").close()

    llm = make_llm(a.provider, a.model)
    tracer = agent.Tracer(trace_path)
    dedupe = agent.DEDUPE_REPEATED_CALLS if a.dedupe is None else a.dedupe
    print(f"label={a.label} provider={a.provider} dedupe={dedupe}\n")

    replies = []
    for s in scenarios:
        result = agent.run_agent(s["sender"], s["message"], llm, tracer,
                                 scenario=s["id"], dedupe=dedupe)
        flags = checks.evaluate(s["expect"], tracer.run, result)
        replies.append({"scenario": s["id"], "sender": s["sender"], "message": s["message"],
                        "steps": result["steps"], "ended_cleanly": result["ended_cleanly"],
                        "cost": result["cost"], "reply": result["reply"], "auto_flags": flags})
        mark = "ok  " if not flags else "FLAG"
        print(f"[{mark}] #{s['id']:>2}  steps={len(tracer.run):<2}  " +
              ("; ".join(flags) if flags else ""))

    if a.only and os.path.exists(replies_path):   # merge a partial rerun into the file
        with open(replies_path, encoding="utf-8") as f:
            old = {r["scenario"]: r for r in json.load(f)}
        old.update({r["scenario"]: r for r in replies})
        replies = [old[k] for k in sorted(old)]
    with open(replies_path, "w", encoding="utf-8") as f:
        json.dump(replies, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {trace_path} and {replies_path}")


if __name__ == "__main__":
    main()
