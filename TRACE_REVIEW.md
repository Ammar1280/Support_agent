# TRACE_REVIEW

Audit of my own support agent against the 20 scenarios in `merik-support-scenarios.md` (v1.1).
Traces: `traces/trace_before.jsonl` (before the fix) and `traces/trace_after.jsonl` (after).
Model/provider used: TODO. Run date: TODO.

How I judged: I read the steps in the trace first and the reply second. A scenario passes only
if the path is sound (right tools, right order, no redundant or repeated calls, one clean
`draft_reply`) and the reply is right (cites the policy, does not promise an action the agent
cannot take, does not leak another customer's order, does not invent anything).

## 1. Verdict for every scenario (before the fix)

Fill in the three TODO columns by reading `traces/summary_before.md`
(`python summarize_traces.py before`). Verdict is one of PASS, PATH FAIL (reply right, path
wrong), REPLY FAIL, or FAIL. Evidence must cite step numbers from `trace_before.jsonl`.

| # | Expected path (from the pack) | Verdict | Evidence (trace steps) | Notes |
|---|---|---|---|---|
| 1 | get_order(A-37) → draft_reply | TODO | TODO | TODO |
| 2 | get_order(A-91) → check_policy(POL-114) → draft_reply | TODO | TODO | TODO |
| 3 | get_order(A-11) → check_policy(POL-101) → draft_reply | TODO | TODO | TODO |
| 4 | get_order(A-42) → check_policy(POL-120) → draft_reply (escalate) | TODO | TODO | TODO |
| 5 | get_order(A-37) → check_policy(POL-120) → draft_reply | TODO | TODO | TODO |
| 6 | get_order(A-66) → check_policy(POL-133) → draft_reply | TODO | TODO | TODO |
| 7 | get_order(A-66) → check_policy(POL-133) → draft_reply | TODO | TODO | TODO |
| 8 | get_order(A-66) → check_policy(POL-133) → draft_reply (escalate) | TODO | TODO | TODO |
| 9 | get_order(A-71) → check_policy(POL-140) → draft_reply (escalate) | TODO | TODO | TODO |
| 10 | get_order(A-99) → draft_reply | TODO | TODO | TODO |
| 11 | draft_reply only | TODO | TODO | TODO |
| 12 | get_order(A-91) → draft_reply | TODO | TODO | TODO |
| 13 | get_order(A-71) → check_policy(POL-140) → draft_reply (escalate) | TODO | TODO | TODO |
| 14 | draft_reply only | TODO | TODO | TODO |
| 15 | get_order(A-23) → check_policy(POL-114) → draft_reply (escalate) | TODO | TODO | TODO |
| 16 | draft_reply only | TODO | TODO | TODO |
| 17 | draft_reply only | TODO | TODO | TODO |
| 18 | get_order(A-91) → draft_reply | TODO | TODO | TODO |
| 19 | get_order(A-11) → get_order(A-23) → get_order(A-58) → check_policy(POL-101) → draft_reply | TODO | TODO | TODO |
| 20 | draft_reply only | TODO | TODO | TODO |

## 2. Runs where the reply was right but the path was not

TODO: at least one scenario. Give its number, the step numbers, what the path did, and what the
pack expected instead.

## 3. Failure modes the loop does not handle

TODO: name at least two, each with the scenario and the step numbers in the trace that show it.
Candidates to check against YOUR traces (keep only what you can point to):
- No detection of repeated identical tool calls (scenario 18).
- No ownership check in code: the other customer's order record is placed in the model's context
  before the model decides to decline (scenario 12).
- Over-fetching policies, or fetching one when the pack expects none (look at 11, 14, 16, 17, 20).
- The step cap ends a run with no `draft_reply` (look for a `run_aborted` step).
- Date arithmetic left to the model (scenarios 3, 15, 19: 8, 26 and 68 days).
- Invalid model output only costs a step and a retry; nothing escalates when it keeps failing.

## 4. The failure mode I fixed

TODO: which one, the scenario that reproduces it, and what I changed.

The fix (keep or adapt after you have applied it): set `DEDUPE_REPEATED_CALLS = True` in `agent.py`. A repeated identical
`(tool, args)` call is not executed; the loop logs a `loop_guard` step and returns the cached
result to the model. Reproduced by scenario 18 and by `test_repeat_call.py`.

## 5. Before / after

TODO: fill from `python summarize_traces.py before after`.

| Scenario | Steps before | Steps after | get_order calls before | get_order calls after |
|---|---|---|---|---|
| 18 | TODO | TODO | TODO | TODO |

Note any scenario whose verdict changed, for better or worse.
