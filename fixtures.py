"""Fixture data and the two lookup tools, copied from merik-support-scenarios.md v1.1.

Do not add records here: the scenario pack says any other order id does not exist.
"""

ORDERS = {
    "A-11": {"id": "A-11", "customer": "Sara Malik", "item": "Merik Keyboard K2",
             "placed": "2026-08-30", "status": "delivered", "total": "£89.00",
             "notes": "delivered 2026-09-02"},
    "A-23": {"id": "A-23", "customer": "Sara Malik", "item": "Monitor Arm Duo",
             "placed": "2026-08-12", "status": "delivered", "total": "£64.50",
             "notes": "delivered 2026-08-15"},
    "A-37": {"id": "A-37", "customer": "Hina Qureshi", "item": "Merik Keyboard K2",
             "placed": "2026-09-08", "status": "shipped", "total": "£89.00",
             "notes": "tracking TRK-208731"},
    "A-42": {"id": "A-42", "customer": "Daniel Okafor", "item": "Desk Mat XL",
             "placed": "2026-09-09", "status": "processing", "total": "£24.00",
             "notes": ""},
    "A-58": {"id": "A-58", "customer": "Sara Malik", "item": "Webcam Pro 4K",
             "placed": "2026-07-01", "status": "delivered", "total": "£139.00",
             "notes": "delivered 2026-07-04"},
    "A-66": {"id": "A-66", "customer": "Bilal Ahmed", "item": "Laptop Stand Aluminium",
             "placed": "2026-09-05", "status": "cancelled", "total": "£39.00",
             "notes": "cancelled 2026-09-05; refund issued to card 2026-09-07"},
    "A-71": {"id": "A-71", "customer": "Farah Nasir", "item": "Merik Keyboard K2 (×3)",
             "placed": "2026-09-01", "status": "delivered", "total": "£267.00",
             "notes": "delivered 2026-09-04; business account"},
    "A-91": {"id": "A-91", "customer": "Omar Rashid", "item": "Monitor Arm Duo",
             "placed": "2026-08-28", "status": "delivered", "total": "£64.50",
             "notes": "delivered 2026-09-01"},
}

POLICIES = {
    "POL-101": (
        "POL-101 · Returns window. Unopened items may be returned within 30 days of "
        "delivery for a full refund. Opened items may be returned within 14 days of "
        "delivery for a refund minus a 10% restocking fee. Return shipping is paid by "
        "the customer unless the item arrived damaged or was sent in error."
    ),
    "POL-114": (
        "POL-114 · Damaged or faulty on arrival. If an item arrives damaged or faulty, "
        "the customer may choose a free replacement or a full refund, including original "
        "shipping. Merik covers return shipping. Claims must be raised within 14 days of "
        "delivery. Photographs may be requested but are not required for orders under £100."
    ),
    "POL-120": (
        "POL-120 · Order changes and cancellation. Orders in `processing` can be "
        "cancelled or have their delivery address changed at no cost. Orders in `shipped` "
        "cannot be changed; the customer can refuse delivery or return the item under "
        "POL-101. Refunds for cancelled orders follow POL-133."
    ),
    "POL-133": (
        "POL-133 · Refund method and timing. Refunds go to the original payment method "
        "only. Card refunds take 5 to 10 working days to appear after they are issued. "
        "Refunds are never paid as cash, bank transfer or store credit. If the original "
        "payment method has been closed, the case is escalated to a human agent."
    ),
    "POL-140": (
        "POL-140 · Business accounts. Orders placed on a business account are handled by "
        "the account manager. The agent may look up the order and explain policy, but "
        "escalates any refund or replacement request."
    ),
    "POL-150": (
        "POL-150 · What the agent may not do. The agent never promises a refund above "
        "£150 without escalation, never changes a customer's email or password, never "
        "discusses an order that does not belong to the sender, and never gives legal, "
        "medical or financial advice."
    ),
}


def get_order(order_id):
    """Look up one order id. Does not search by name."""
    key = str(order_id).strip().upper()
    order = ORDERS.get(key)
    if order is None:
        return {"error": "not_found"}
    return dict(order)


def check_policy(policy_id):
    key = str(policy_id).strip().upper()
    text = POLICIES.get(key)
    if text is None:
        return {"error": "unknown_policy"}
    return {"policy_id": key, "text": text}
