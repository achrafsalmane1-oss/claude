"""Inbound webhooks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app import billing
from app.deps import SessionDep, SettingsDep
from app.log import logger

router = APIRouter(prefix="/webhooks", include_in_schema=False)


@router.post("/stripe")
async def stripe_webhook(request: Request, settings: SettingsDep, session: SessionDep):
    """Apply Stripe subscription lifecycle events to local account state."""
    if not settings.billing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Billing is not configured."
        )

    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    try:
        event = billing.verify_webhook(settings, payload, signature)
    except billing.BillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    outcome = billing.handle_event(session, event)
    session.commit()

    logger.info(
        "stripe webhook handled", extra={"event": event.get("type"), "outcome": outcome}
    )
    return {"received": True, "outcome": outcome}
