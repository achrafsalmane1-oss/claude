"""The commercial plan catalog.

Prices are in whole USD per month. Edit this file to reprice; the marketing
page, quota enforcement and Stripe checkout all read from here so the catalog
never drifts between what you advertise and what you enforce.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_usd: int
    monthly_credits: int
    max_seats: int
    max_depth: int
    api_access: bool
    email_enrichment: bool
    blurb: str
    highlights: list[str] = field(default_factory=list)
    featured: bool = False

    @property
    def is_free(self) -> bool:
        return self.price_usd == 0

    @property
    def price_label(self) -> str:
        return "Free" if self.is_free else f"${self.price_usd}"


PLANS: dict[str, Plan] = {
    "free": Plan(
        code="free",
        name="Trial",
        price_usd=0,
        monthly_credits=100,
        max_seats=1,
        max_depth=2,
        api_access=False,
        email_enrichment=False,
        blurb="Kick the tyres on a real search before you pay anything.",
        highlights=[
            "100 leads per month",
            "Dashboard search + CSV export",
            "1 seat",
        ],
    ),
    "starter": Plan(
        code="starter",
        name="Starter",
        price_usd=49,
        monthly_credits=5_000,
        max_seats=2,
        max_depth=10,
        api_access=True,
        email_enrichment=False,
        blurb="For one agency or SDR building lists week to week.",
        highlights=[
            "5,000 leads per month",
            "REST API + API keys",
            "2 seats",
            "CSV export, unlimited searches",
        ],
    ),
    "growth": Plan(
        code="growth",
        name="Growth",
        price_usd=149,
        monthly_credits=25_000,
        max_seats=10,
        max_depth=25,
        api_access=True,
        email_enrichment=True,
        blurb="For teams running outbound at volume across many cities.",
        highlights=[
            "25,000 leads per month",
            "Website email enrichment",
            "REST API + API keys",
            "10 seats",
            "Priority support",
        ],
        featured=True,
    ),
    "scale": Plan(
        code="scale",
        name="Scale",
        price_usd=399,
        monthly_credits=100_000,
        max_seats=50,
        max_depth=50,
        api_access=True,
        email_enrichment=True,
        blurb="For data resellers and platforms embedding lead data.",
        highlights=[
            "100,000 leads per month",
            "Website email enrichment",
            "Deep pagination (50 pages)",
            "50 seats",
            "Priority queue",
        ],
    ),
}

DEFAULT_PLAN = "free"

# Order used everywhere the plans are listed to a customer.
PLAN_ORDER = ["free", "starter", "growth", "scale"]


def get_plan(code: str) -> Plan:
    """Return the plan for ``code``, falling back to the default plan.

    Falling back rather than raising matters: if a plan is retired from the
    catalog, existing accounts must keep working rather than 500.
    """
    return PLANS.get(code, PLANS[DEFAULT_PLAN])


def listed_plans() -> list[Plan]:
    return [PLANS[code] for code in PLAN_ORDER if code in PLANS]


def paid_plans() -> list[Plan]:
    return [plan for plan in listed_plans() if not plan.is_free]
