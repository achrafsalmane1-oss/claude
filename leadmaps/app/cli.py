"""Command line administration.

    python -m app.cli create-admin --email you@example.com
    python -m app.cli set-plan --email you@example.com --plan growth
    python -m app.cli list-accounts

Run it against the same DATABASE_URL the app uses.
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from sqlalchemy import select

from app import services
from app.db import init_db, session_scope
from app.models import Account, User
from app.plans import PLANS
from app.security import hash_password, password_problem

ADMIN_PLAN = "internal"


def _prompt_password() -> str:
    """Ask twice, or generate one if the operator just presses enter."""
    first = getpass.getpass("Password (blank to generate one): ")
    if not first:
        generated = secrets.token_urlsafe(18)
        print(f"Generated password: {generated}")
        return generated
    if first != getpass.getpass("Confirm password: "):
        sys.exit("Passwords did not match.")
    return first


def create_admin(args: argparse.Namespace) -> int:
    password = args.password or _prompt_password()

    problem = password_problem(password)
    if problem:
        sys.exit(problem)

    with session_scope() as session:
        existing = services.find_user_by_email(session, args.email)

        if existing is not None:
            # Promote rather than refuse: re-running this is how you fix a
            # locked-out admin.
            existing.password_hash = hash_password(password)
            existing.is_staff = True
            existing.account.plan_code = ADMIN_PLAN
            existing.account.subscription_status = "active"
            print(f"Promoted existing user {existing.email} to an unlimited admin account.")
        else:
            user = services.create_account_with_owner(
                session,
                email=args.email,
                password=password,
                company_name=args.company,
                plan_code=ADMIN_PLAN,
            )
            user.is_staff = True
            user.account.subscription_status = "active"
            print(f"Created unlimited admin account for {user.email}.")

    print("\nSign in at /login with that email and password.")
    print("Plan: Internal — no lead cap, every feature unlocked, API access on.")
    return 0


def set_plan(args: argparse.Namespace) -> int:
    if args.plan not in PLANS:
        sys.exit(f"Unknown plan '{args.plan}'. Known plans: {', '.join(PLANS)}")

    with session_scope() as session:
        user = services.find_user_by_email(session, args.email)
        if user is None:
            sys.exit(f"No user with email {args.email}.")
        user.account.plan_code = args.plan
        user.account.subscription_status = "active"
        print(f"{user.email} is now on the {PLANS[args.plan].name} plan.")
    return 0


def list_accounts(_: argparse.Namespace) -> int:
    with session_scope() as session:
        rows = session.scalars(select(User).join(Account).order_by(User.created_at)).all()
        if not rows:
            print("No accounts yet.")
            return 0
        width = max(len(user.email) for user in rows)
        for user in rows:
            flag = " [staff]" if user.is_staff else ""
            print(f"{user.email:<{width}}  {user.account.plan_code}{flag}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="create or promote an unlimited admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", default="", help="omit to be prompted")
    admin.add_argument("--company", default="Internal")
    admin.set_defaults(func=create_admin)

    plan = sub.add_parser("set-plan", help="move an existing account onto a plan")
    plan.add_argument("--email", required=True)
    plan.add_argument("--plan", required=True, choices=sorted(PLANS))
    plan.set_defaults(func=set_plan)

    listing = sub.add_parser("list-accounts", help="show every account and its plan")
    listing.set_defaults(func=list_accounts)

    args = parser.parse_args(argv)
    init_db()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
