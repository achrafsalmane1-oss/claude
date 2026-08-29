"""Application settings, loaded from the environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Every value has a development-friendly default so that ``uvicorn app.main:app``
    works on a clean checkout. Production deployments must override at minimum
    ``secret_key``, ``database_url`` and the Stripe credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Branding -------------------------------------------------------
    brand_name: str = "LeadMaps"
    brand_tagline: str = "Local business lead lists, on tap."
    support_email: str = "support@example.com"
    public_url: str = "http://localhost:8000"

    # --- Core -----------------------------------------------------------
    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./leadmaps.db"
    session_cookie: str = "lm_session"
    session_max_age: int = 60 * 60 * 24 * 14  # 14 days
    debug: bool = False

    # --- Scraping engine -------------------------------------------------
    # "local" shells out to the google-maps-scraper CLI for real data with no
    #         extra infrastructure. This is the default.
    # "http"  talks to a full google-maps-scraper SaaS deployment (queue,
    #         workers, admin UI) — the right choice at volume.
    # "mock"  is a built-in fake engine for tests and UI work. Never sell it.
    engine_mode: str = "local"
    engine_url: str = "http://localhost:8080"
    engine_api_key: str = ""
    engine_timeout: float = 30.0
    engine_poll_interval: int = 10

    # --- Local engine ----------------------------------------------------
    # Path to a google-maps-scraper binary. If empty, the scraper runs via
    # Docker instead, which needs nothing installed but Docker itself.
    engine_binary: str = ""
    engine_docker_image: str = "gosom/google-maps-scraper:latest"
    engine_workdir: str = "./scrape-jobs"
    # Wall-clock ceiling for one search. Deep searches are slow; browser work is.
    engine_job_timeout: int = 1800
    # Passed through to the scraper's -c flag (parallel browser workers).
    engine_concurrency: int = 4
    # Comma-separated proxies. Strongly recommended at any real volume.
    engine_proxies: str = ""

    # --- Billing ---------------------------------------------------------
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    # Map of plan code -> Stripe price id, e.g. "starter=price_123,growth=price_456"
    stripe_prices: str = ""

    # --- Limits ----------------------------------------------------------
    signup_enabled: bool = True
    max_concurrent_jobs: int = 5

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key)

    def price_id(self, plan_code: str) -> str:
        """Return the Stripe price id configured for ``plan_code``."""
        for pair in self.stripe_prices.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            code, _, price = pair.partition("=")
            if code.strip() == plan_code:
                return price.strip()
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
