"""Public marketing and documentation pages."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.deps import OptionalUserDep, SettingsDep, render
from app.plans import listed_plans

router = APIRouter()

TERMS_BODY = """
<h2>1. The service</h2>
<p>We collect publicly listed business information from online map listings on your
instruction and deliver it to you as structured data.</p>

<h2>2. Your responsibilities</h2>
<p>You are responsible for how you use the data we deliver, including compliance with
data-protection law (such as GDPR and the UK GDPR), electronic-marketing rules (such as
PECR and CAN-SPAM), and any applicable do-not-call registries. You must not use the data
to harass, defraud, or unlawfully profile anyone.</p>

<h2>3. Acceptable use</h2>
<p>You may not resell raw access to the service, attempt to circumvent your plan's
allowance, or use the service to build a competing scraping product.</p>

<h2>4. Plans and billing</h2>
<p>Plans are billed monthly in advance. Lead allowances reset each billing period and do
not roll over. Cancel any time; access continues to the end of the period you have paid
for. We do not offer pro-rated refunds for partial months.</p>

<h2>5. Availability</h2>
<p>We aim for high availability but do not guarantee uninterrupted service. Searches that
fail are not charged against your allowance.</p>

<h2>6. Liability</h2>
<p>To the maximum extent permitted by law, our aggregate liability is limited to the fees
you paid us in the three months preceding the claim.</p>

<h2>7. Changes</h2>
<p>We may update these terms; material changes will be announced by email at least 14
days before they take effect.</p>
"""

PRIVACY_BODY = """
<h2>What we store about you</h2>
<p>Your email address, a hashed password, your company name, and your billing identifiers
held by our payment processor. We never see or store your card details.</p>

<h2>What we store about your searches</h2>
<p>The search terms you submit and the results returned, so that you can re-download them.
You can delete a search and its results at any time from the dashboard.</p>

<h2>Business contact data</h2>
<p>Results consist of publicly listed business information. Where a listing contains
personal data (for example, a sole trader's name or a personal phone number), you act as
the data controller for any subsequent processing you carry out, and we act as a
processor on your instructions.</p>

<h2>Processors we use</h2>
<p>Payment processing (Stripe) and our hosting provider. Both are bound by data-processing
agreements.</p>

<h2>Retention</h2>
<p>Search results are retained while your account is open. Close your account and we will
delete your data within 30 days.</p>

<h2>Your rights</h2>
<p>Email us to access, export, correct or delete your personal data.</p>
"""


def page_context(request: Request, settings, user, **extra) -> dict:
    from datetime import datetime, timezone

    context = {
        "request": request,
        "brand": settings.brand_name,
        "tagline": settings.brand_tagline,
        "support_email": settings.support_email,
        "public_url": settings.public_url,
        "user": user,
        "plans": listed_plans(),
        "year": datetime.now(timezone.utc).year,
    }
    context.update(extra)
    return context


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, settings: SettingsDep, user: OptionalUserDep):
    return render(
        "landing.html", page_context(request, settings, user)
    )


@router.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request, settings: SettingsDep, user: OptionalUserDep):
    return render(
        "pricing.html", page_context(request, settings, user)
    )


@router.get("/docs", response_class=HTMLResponse)
def docs(request: Request, settings: SettingsDep, user: OptionalUserDep):
    return render("docs.html", page_context(request, settings, user))


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request, settings: SettingsDep, user: OptionalUserDep):
    return render(
        "legal.html",
        page_context(
            request,
            settings,
            user,
            heading="Terms of service",
            updated="August 2026",
            body=TERMS_BODY,
        ),
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, settings: SettingsDep, user: OptionalUserDep):
    return render(
        "legal.html",
        page_context(
            request,
            settings,
            user,
            heading="Privacy policy",
            updated="August 2026",
            body=PRIVACY_BODY,
        ),
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots(settings: SettingsDep) -> str:
    return f"User-agent: *\nAllow: /\nDisallow: /app/\nSitemap: {settings.public_url}/sitemap.xml\n"


@router.get("/sitemap.xml")
def sitemap(settings: SettingsDep):
    paths = ["/", "/pricing", "/docs", "/terms", "/privacy"]
    urls = "".join(
        f"<url><loc>{settings.public_url}{path}</loc></url>" for path in paths
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    from fastapi.responses import Response

    return Response(content=body, media_type="application/xml")


@router.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"
