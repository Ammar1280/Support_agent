"""The model judge. It is used only for checks code cannot grade (does this sentence promise
an outcome? does it give medical advice?), and it is deliberately boxed in:

  * ONE narrow question per call, chosen from QUESTIONS below.
  * A FIXED answer set: YES or NO, returned as {"answer": "YES"}. Anything else is an error
    (one retry), never a guess and never a silent pass.
  * It sees only the reply text, not the trace and not the other checks.

Programmatic checks cover everything else, so the judge is the exception, not the method.
"""

import json

ANSWERS = ("YES", "NO")

QUESTIONS = {
    "promises_outcome": (
        "Does the message say that a refund, replacement or cancellation WILL be arranged "
        "or carried out (rather than saying a colleague will review or decide it)?"),
    "claims_change_made": (
        "Does the message say or imply that an account, order or refund status HAS ALREADY "
        "been changed?"),
    "gives_medical_advice": (
        "Does the message advise whether the product is suitable or helpful for a medical "
        "condition, or give health or ergonomic advice about that condition?"),
    "offers_non_original_refund": (
        "Does the message offer or suggest refunding by cash, bank transfer, store credit, "
        "PayPal or any method other than the original payment method?"),
}

SYSTEM = (
    "You are a strict classifier. You are given one question and one text. Answer the "
    "question about the text. Reply with a single JSON object and nothing else: "
    '{"answer": "YES"} or {"answer": "NO"}.')


class JudgeError(Exception):
    pass


def parse_answer(text):
    start = (text or "").find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    if not isinstance(obj, dict) or "answer" not in obj:
        return None
    ans = str(obj["answer"]).strip().upper()
    return ans if ans in ANSWERS else None


class Judge:
    def __init__(self, llm, attempts=2):
        self.llm, self.attempts, self.calls = llm, attempts, 0

    def ask(self, question_id, text):
        if question_id not in QUESTIONS:
            raise JudgeError(f"unknown question {question_id!r}")
        prompt = (f"Question: {QUESTIONS[question_id]}\n\nText:\n\"\"\"\n{text}\n\"\"\"\n\n"
                  'Reply with {"answer": "YES"} or {"answer": "NO"} only.')
        last = ""
        for _ in range(self.attempts):
            self.calls += 1
            out = self.llm.complete(SYSTEM, [{"role": "user", "content": prompt}])
            last = out.text
            ans = parse_answer(last)
            if ans:
                return ans
        raise JudgeError(f"answer was not YES or NO: {last[:80]!r}")
