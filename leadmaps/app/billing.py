"""Stripe subscription billing.

When ``STRIPE_SECRET_KEY`` is unset the app runs in *billing-disabled* mode:
plan changes apply immediately without payment. That keeps local development
and demos frictionless. Set the key and the price ids and the same UI starts
charging real money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Account
from app.plans import PLANS, get_plan

# Stripe subscription statuses that entitle an account to its paid plan.
ENTITLED_STATUSES = {"active", "trialing", "past_due"}


class BillingError(Exception):
    """A billing operation could not be completed."""


@dataclass(frozen=True)
class CheckoutLink:
    url: str


def _configure(settings: Settings) -> None:
    stripe.api_key = settings.stripe_secret_key


def ensure_customer(settings: Settings, session: Session, account: Account, email: str) -> str:
    """Return the account's Stripe customer id, creating it on first use."""
    if account.stripe_customer_id:
        return account.stripe_customer_id

    _configure(settings)
    try:
        customer = stripe.Customer.create(
            email=email,
            name=account.name,
            metadata={"account_id": account.id},
        )
    except stripe.StripeError as exc:  # pragma: no cover - network path
        raise BillingError(str(exc)) from exc

    account.stripe_customer_id = customer["id"]
    session.flush()
    return account.stripe_customer_id


def create_checkout_session(
    settings: Settings,
    session: Session,
    account: Account,
    *,
    plan_code: str,
    email: str,
) -> CheckoutLink:
    """Start a Stripe Checkout for ``plan_code``."""
    plan = PLANS.get(plan_code)
    if plan is None or plan.is_free:
        raise BillingError("That plan cannot be purchased.")

    price_id = settings.price_id(plan_code)
    if not price_id:
        raise BillingError(
            f"No Stripe price is configured for the {plan.name} plan. "
            "Set STRIPE_PRICES in your environment."
        )

    customer_id = ensure_customer(settings, session, account, email)

    _configure(settings)
    try:
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.public_url}/app/billing?checkout=success",
            cancel_url=f"{settings.public_url}/app/billing?checkout=cancelled",
            allow_promotion_codes=True,
            client_reference_id=account.id,
            subscription_data={"metadata": {"account_id": account.id, "plan_code": plan_code}},
            metadata={"account_id": account.id, "plan_code": plan_code},
        )
    except stripe.StripeError as exc:  # pragma: no cover - network path
        raise BillingError(str(exc)) from exc

    return CheckoutLink(url=checkout["url"])


def create_portal_session(settings: Settings, account: Account) -> CheckoutLink:
    """Open the Stripe billing portal so the customer can self-serve."""
    if not account.stripe_customer_id:
        raise BillingError("This account has no billing history yet.")

    _configure(settings)
    try:
        portal = stripe.billing_portal.Session.create(
            customer=account.stripe_customer_id,
            return_url=f"{settings.public_url}/app/billing",
        )
    except stripe.StripeError as exc:  # pragma: no cover - network path
        raise BillingError(str(exc)) from exc

    return CheckoutLink(url=portal["url"])


def verify_webhook(settings: Settings, payload: bytes, signature: str) -> dict:
    """Verify and decode a Stripe webhook payload."""
    if not settings.stripe_webhook_secret:
        raise BillingError("STRIPE_WEBHOOK_SECRET is not configured.")
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise BillingError("Invalid webhook signature.") from exc
    return dict(event)


def handle_event(session: Session, event: dict) -> str:
    """Apply a Stripe event to local state. Returns a short outcome label."""
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        return _apply_checkout(session, obj)
    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        return _apply_subscription(session, obj)
    if event_type == "customer.subscription.deleted":
        return _apply_cancellation(session, obj)
    if event_type == "invoice.payment_failed":
        return _apply_payment_failure(session, obj)

    return "ignored"


def _find_account(session: Session, *, account_id: str = "", customer_id: str = "") -> Account | None:
    if account_id:
        account = session.get(Account, account_id)
        if account is not None:
            return account
    if customer_id:
        return session.scalar(
            select(Account).where(Account.stripe_customer_id == customer_id)
        )
    return None


def _apply_checkout(session: Session, obj: dict) -> str:
    metadata = obj.get("metadata") or {}
    account = _find_account(
        session,
        account_id=metadata.get("account_id") or obj.get("client_reference_id") or "",
        customer_id=obj.get("customer") or "",
    )
    if account is None:
        return "account_not_found"

    if not account.stripe_customer_id and obj.get("customer"):
        account.stripe_customer_id = obj["customer"]
    if obj.get("subscription"):
        account.stripe_subscription_id = obj["subscription"]

    plan_code = metadata.get("plan_code", "")
    if plan_code in PLANS:
        account.plan_code = plan_code
    account.subscription_status = "active"
    return "checkout_applied"


def _apply_subscription(session: Session, obj: dict) -> str:
    metadata = obj.get("metadata") or {}
    account = _find_account(
        session,
        account_id=metadata.get("account_id", ""),
        customer_id=obj.get("customer") or "",
    )
    if account is None:
        return "account_not_found"

    account.stripe_subscription_id = obj.get("id", account.stripe_subscription_id)
    status = obj.get("status", "")
    account.subscription_status = status or account.subscription_status

    plan_code = metadata.get("plan_code") or _plan_from_items(obj)
    if plan_code in PLANS and status in ENTITLED_STATUSES:
        account.plan_code = plan_code

    if status not in ENTITLED_STATUSES:
        account.plan_code = "free"

    period_end = obj.get("current_period_end")
    if isinstance(period_end, int):
        account.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    return "subscription_applied"


def _apply_cancellation(session: Session, obj: dict) -> str:
    account = _find_account(session, customer_id=obj.get("customer") or "")
    if account is None:
        return "account_not_found"
    account.plan_code = "free"
    account.subscription_status = "canceled"
    account.stripe_subscription_id = ""
    return "subscription_cancelled"


def _apply_payment_failure(session: Session, obj: dict) -> str:
    account = _find_account(session, customer_id=obj.get("customer") or "")
    if account is None:
        return "account_not_found"
    account.subscription_status = "past_due"
    return "payment_failed"


def _plan_from_items(subscription: dict) -> str:
    """Best-effort plan lookup from the subscription's price id."""
    from app.config import get_settings

    settings = get_settings()
    items = ((subscription.get("items") or {}).get("data")) or []
    for item in items:
        price_id = ((item.get("price") or {}).get("id")) or ""
        if not price_id:
            continue
        for code in PLANS:
            if settings.price_id(code) == price_id:
                return code
    return ""


def apply_plan_without_payment(session: Session, account: Account, plan_code: str) -> None:
    """Development path used when billing is disabled."""
    plan = get_plan(plan_code)
    account.plan_code = plan.code
    account.subscription_status = "active" if not plan.is_free else "trialing"
    session.flush()
