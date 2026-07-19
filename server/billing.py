"""Billing for Colddrops.

Plan catalog + Stripe Checkout. Works in two modes:
  - live : real Stripe Checkout + webhook (needs STRIPE_SECRET_KEY + price ids)
  - stub : no Stripe configured — checkout upgrades the workspace immediately and
           returns a local success URL, so the upgrade flow is testable now.
"""
import os

PLANS = {
    "starter": {"name": "Starter", "price_usd": 90, "drops": 1000,
                "blurb": "1,000 voice drops / mo"},
    "growth":  {"name": "Growth",  "price_usd": 290, "drops": 5000,
                "blurb": "5,000 voice drops / mo"},
    "scale":   {"name": "Scale",   "price_usd": 690, "drops": 15000,
                "blurb": "15,000 voice drops / mo"},
}

STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def price_id(plan: str) -> str:
    return os.environ.get(f"STRIPE_PRICE_{plan.upper()}", "")


def live() -> bool:
    return bool(STRIPE_KEY)


def plan_catalog() -> list[dict]:
    return [{"id": k, **v} for k, v in PLANS.items()]


def create_checkout(workspace_id: int, plan: str, email: str) -> dict:
    """Return {url, stub}. In stub mode the caller applies the plan directly."""
    if plan not in PLANS:
        raise ValueError("unknown plan")
    if not live() or not price_id(plan):
        return {"url": f"{PUBLIC_BASE}/app.html?upgraded={plan}", "stub": True, "plan": plan}
    import stripe
    stripe.api_key = STRIPE_KEY
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id(plan), "quantity": 1}],
        customer_email=email,
        client_reference_id=str(workspace_id),
        metadata={"workspace_id": workspace_id, "plan": plan},
        success_url=f"{PUBLIC_BASE}/app.html?upgraded={plan}",
        cancel_url=f"{PUBLIC_BASE}/app.html?billing=cancelled",
    )
    return {"url": session.url, "stub": False, "plan": plan}


def verify_and_parse_webhook(raw_body: bytes, signature: str) -> dict | None:
    """Return {workspace_id, plan} for a completed checkout, else None."""
    if live() and STRIPE_WEBHOOK_SECRET:
        import stripe
        try:
            event = stripe.Webhook.construct_event(raw_body, signature, STRIPE_WEBHOOK_SECRET)
        except Exception:
            return None
    else:
        import json
        try:
            event = json.loads(raw_body)
        except Exception:
            return None
    if event.get("type") != "checkout.session.completed":
        return None
    obj = event.get("data", {}).get("object", {})
    meta = obj.get("metadata", {}) or {}
    wid = meta.get("workspace_id") or obj.get("client_reference_id")
    plan = meta.get("plan")
    if wid and plan in PLANS:
        return {"workspace_id": int(wid), "plan": plan}
    return None
