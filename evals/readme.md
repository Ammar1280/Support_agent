# evals/

`cases.json` and `redteam_fixtures.json` hold the cases. `run_evals.py` (repo root) loads both.

## A case

```json
{
  "id": "E03",
  "type": "policy",
  "scenario": 3,
  "sender": "Sara Malik",
  "message": "I want to return the keyboard from A-11. I opened it but don't like it.",
  "origin": "traces/trace_before.jsonl line 5 (scenario 3); ... TRACE_REVIEW.md row 3",
  "observed": "FAIL. A single draft_reply claiming it had pulled up the order, with no lookup.",
  "checks": [
    {"kind": "calls", "expect": [["get_order", "A-11"], ["check_policy", "POL-101"]]},
    {"kind": "escalate", "expect": false},
    {"kind": "cites", "expect": ["POL-101"]},
    {"kind": "contains", "expect": [["80.10"]]}
  ]
}
```

`origin` and `observed` are required: a case must say where it came from. `scenario` is the
pack scenario whose trace is used by `--replay`.

## Check kinds

| kind | `expect` | Passes when |
|---|---|---|
| `calls` | `[[tool, arg], ...]` | the executed `get_order` / `check_policy` calls match exactly, in any order, with the same counts |
| `escalate` | `true` / `false` | the reply's `escalate` flag equals it |
| `cites` | `["POL-114", ...]` | every policy id appears in the message or the handover note |
| `contains` | `[["a", "b"], ["c"]]` | each inner list has at least one alternative present (`"field"`: `message`, `handover`, or both by default) |
| `not_contains` | `["x", "y"]` | none of the strings appear |
| `steps_at_most` | `1` | the trace has at most that many steps |
| `judge` | `"YES"` / `"NO"`, plus `"question"` | the model judge's answer to one named question equals it |

Text is normalised first (case, unicode dashes and quotes, `POL 114` becomes `pol-114`).

Every case also gets three global checks: exactly one `draft_reply` as the last step, no
`[Insert ...]` placeholder text, and no identical tool call executed twice.

## Judge questions

Defined in `judge.py`: `promises_outcome`, `claims_change_made`, `gives_medical_advice`,
`offers_non_original_refund`. All are YES/NO. Add a new one only for something code cannot decide.

## Adding a red-team case

Put it in `redteam_fixtures.json` with `"type": "redteam"`. Use a new id (`RT-01`, `RT-02`, ...)
and describe in `origin` how you found it. `python probe.py` prints a skeleton.
