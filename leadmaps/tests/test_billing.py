"""Subscription lifecycle: plan changes and Stripe webhook handling."""

import pytest

from app import billing
from app.models import Account
from tests.conftest import upgrade


def account_row(client) -> Account:
    """Read the single account straight out of the database."""
    import app.db as db_module
    from sqlalchemy import select

    with db_module.SessionLocal() as session:
        return session.scalar(select(Account))


def test_new_accounts_start_on_the_free_plan(account):
    assert account_row(account).plan_code == "free"
    assert "Trial plan" in account.get("/app/billing").text


def test_plan_change_applies_directly_when_billing_is_disabled(account):
    upgrade(account, "growth")
    row = account_row(account)
    assert row.plan_code == "growth"
    assert row.subscription_status == "active"


def test_billing_page_flags_that_stripe_is_not_configured(account):
    assert "Stripe is not configured" in account.get("/app/billing").text


def test_unknown_plan_is_rejected(account):
    response = account.get("/app/billing/checkout?plan=platinum")
    assert "Unknown plan" in response.text


def test_downgrading_back_to_free_works(account):
    upgrade(account, "scale")
    upgrade(account, "free")
    assert account_row(account).plan_code == "free"


def test_webhook_is_unavailable_without_stripe_configured(client):
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 503


# --- Pure webhook handling, exercised without a live Stripe -----------------


@pytest.fixture()
def db_account(client):
    import app.db as db_module

    with db_module.SessionLocal() as session:
        account = Account(name="Webhook Co", stripe_customer_id="cus_123")
        session.add(account)
        session.commit()
        return account.id


def apply(event: dict, account_id: str) -> tuple[str, Account]:
    import app.db as db_module

    with db_module.SessionLocal() as session:
        outcome = billing.handle_event(session, event)
        session.commit()
        return outcome, session.get(Account, account_id)


def test_checkout_completed_activates_the_purchased_plan(db_account):
    outcome, account = apply(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "subscription": "sub_456",
                    "client_reference_id": db_account,
                    "metadata": {"account_id": db_account, "plan_code": "growth"},
                }
            },
        },
        db_account,
    )
    assert outcome == "checkout_applied"
    assert account.plan_code == "growth"
    assert account.subscription_status == "active"
    assert account.stripe_subscription_id == "sub_456"


def test_subscription_update_keeps_the_plan_while_entitled(db_account):
    _, account = apply(
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_456",
                    "customer": "cus_123",
                    "status": "active",
                    "current_period_end": 1800000000,
                    "metadata": {"account_id": db_account, "plan_code": "scale"},
                }
            },
        },
        db_account,
    )
    assert account.plan_code == "scale"
    assert account.current_period_end is not None


def test_a_lapsed_subscription_drops_the_account_to_free(db_account):
    apply(
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_456",
                    "customer": "cus_123",
                    "status": "active",
                    "metadata": {"account_id": db_account, "plan_code": "scale"},
                }
            },
        },
        db_account,
    )
    _, account = apply(
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_456",
                    "customer": "cus_123",
                    "status": "incomplete_expired",
                    "metadata": {"account_id": db_account, "plan_code": "scale"},
                }
            },
        },
        db_account,
    )
    assert account.plan_code == "free"


def test_cancellation_drops_the_account_to_free(db_account):
    outcome, account = apply(
        {
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_123", "id": "sub_456"}},
        },
        db_account,
    )
    assert outcome == "subscription_cancelled"
    assert account.plan_code == "free"
    assert account.subscription_status == "canceled"


def test_a_failed_payment_marks_the_account_past_due(db_account):
    _, account = apply(
        {
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_123"}},
        },
        db_account,
    )
    assert account.subscription_status == "past_due"
    assert account.is_delinquent


def test_a_past_due_account_cannot_start_a_search(account):
    import app.db as db_module
    from sqlalchemy import select

    with db_module.SessionLocal() as session:
        row = session.scalar(select(Account))
        row.subscription_status = "past_due"
        session.commit()

    response = account.post("/app/search", data={"keyword": "cafes", "max_depth": "1"})
    assert "payment failed" in response.text


def test_events_for_unknown_customers_are_ignored(db_account):
    outcome, _ = apply(
        {
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_does_not_exist"}},
        },
        db_account,
    )
    assert outcome == "account_not_found"


def test_unrelated_events_are_ignored(db_account):
    outcome, _ = apply({"type": "ping", "data": {"object": {}}}, db_account)
    assert outcome == "ignored"
