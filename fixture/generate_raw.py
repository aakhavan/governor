"""Write the raw SaaS billing CSVs.

Seed 42 and the de_DE Faker locale are fixed. A second run writes the same
bytes. Dates use a separate Random instance so they do not move if a Faker
call is added later.

_loaded_at is not in the CSVs. load_raw.py stamps it when the warehouse is
loaded, so source freshness stays inside the 12 hour warn window on the day
of the build. The business dates below stay in the past.

History is 1 Apr 2025 through 30 Sep 2026 (18 months). The MRR month spine
in the dbt project uses the same start and 2026-09-01 as the last month.
Change those dates together (dbt_project.yml vars window_start and
window_month_end).
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

SEED = 42
LOCALE = "de_DE"

N_ACCOUNTS = 2000
N_SUBSCRIPTIONS = 3000
N_INVOICES = 30000
N_PAYMENTS = 28000
N_INVOICES_ONE_PAYMENT = 25000
N_INVOICES_TWO_PAYMENTS = 1500
N_VOID_INVOICES = 500

# Exclusive end, so the last included moment is 2026-09-30 23:59:59.
WINDOW_START = datetime(2025, 4, 1)
WINDOW_END = datetime(2026, 10, 1)
ACCOUNT_CREATED_END = datetime(2026, 4, 1)

# status values must match the accepted_values tests in the dbt project.
SUBSCRIPTION_STATUSES = ("active", "cancelled", "past_due")
INVOICE_STATUSES = ("open", "paid", "void")
METHODS = ("card", "sepa", "bank_transfer")

# monthly price in euro cents. Integers so splits of a payment add back exactly.
PLANS = (
    ("plan_free", "Free", 0),
    ("plan_starter", "Starter", 2900),
    ("plan_growth", "Growth", 9900),
    ("plan_business", "Business", 24900),
    ("plan_scale", "Scale", 49900),
    ("plan_enterprise", "Enterprise", 79900),
)

PLAN_COLUMNS = ("plan_id", "plan_name", "monthly_price_eur")
ACCOUNT_COLUMNS = (
    "account_id",
    "company_name",
    "contact_name",
    "contact_email",
    "country",
    "created_at",
)
SUBSCRIPTION_COLUMNS = (
    "subscription_id",
    "account_id",
    "plan_id",
    "status",
    "started_at",
    "cancelled_at",
)
INVOICE_COLUMNS = (
    "invoice_id",
    "subscription_id",
    "account_id",
    "issued_at",
    "amount_eur",
    "status",
)
PAYMENT_COLUMNS = (
    "payment_id",
    "invoice_id",
    "paid_at",
    "amount_eur",
    "method",
    "card_last4",
)

FIXTURE_DIR = Path(__file__).resolve().parent
RAW_DIR = FIXTURE_DIR / "raw"

FILES = {
    "plans.csv": PLAN_COLUMNS,
    "accounts.csv": ACCOUNT_COLUMNS,
    "subscriptions.csv": SUBSCRIPTION_COLUMNS,
    "invoices.csv": INVOICE_COLUMNS,
    "payments.csv": PAYMENT_COLUMNS,
}


def _check_volumes() -> None:
    payments = N_INVOICES_ONE_PAYMENT + 2 * N_INVOICES_TWO_PAYMENTS
    if payments != N_PAYMENTS:
        raise RuntimeError(f"payment count adds up to {payments}, not {N_PAYMENTS}")
    touched = N_INVOICES_ONE_PAYMENT + N_INVOICES_TWO_PAYMENTS + N_VOID_INVOICES
    if touched > N_INVOICES:
        raise RuntimeError("invoice slices run past the invoice count")


def _seeded() -> tuple[random.Random, Faker]:
    # Random(SEED) is independent of Faker's generator.
    rng = random.Random(SEED)
    Faker.seed(SEED)
    return rng, Faker(LOCALE)


def _stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def _parse_money(value: str) -> int:
    euros, cents = value.split(".")
    return int(euros) * 100 + int(cents)


def _random_dt(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """start inclusive, end exclusive. end == start returns start."""
    seconds = int((end - start).total_seconds())
    if seconds <= 0:
        return start
    return start + timedelta(seconds=rng.randrange(seconds))


def _clean(value: str) -> str:
    return " ".join(value.split())


def _plans() -> list[dict[str, str]]:
    return [
        {
            "plan_id": plan_id,
            "plan_name": name,
            "monthly_price_eur": _money(cents),
        }
        for plan_id, name, cents in PLANS
    ]


def _accounts(rng: random.Random, fake: Faker) -> list[dict[str, str]]:
    rows = []
    for number in range(1, N_ACCOUNTS + 1):
        created = _random_dt(rng, WINDOW_START, ACCOUNT_CREATED_END)
        rows.append(
            {
                "account_id": f"acc_{number:05d}",
                "company_name": _clean(fake.company()) or f"Firma {number}",
                "contact_name": _clean(fake.name()) or f"Kontakt {number}",
                "contact_email": _clean(fake.email()),
                "country": _clean(fake.country()) or "Deutschland",
                "created_at": _stamp(created),
            }
        )
    return rows


def _subscriptions(accounts: list[dict[str, str]], rng: random.Random) -> list[dict[str, str]]:
    rows = []
    for number in range(1, N_SUBSCRIPTIONS + 1):
        account = accounts[rng.randrange(len(accounts))]
        plan_id, _name, _cents = PLANS[rng.randrange(len(PLANS))]
        created = datetime.strptime(account["created_at"], "%Y-%m-%d %H:%M:%S")
        started = _random_dt(rng, created, WINDOW_END)
        cancelled_at = ""
        roll = rng.random()
        # One draw decides the status so every row consumes the same calls
        # except the extra date used only when the subscription is cancelled.
        if roll < 0.30 and started + timedelta(days=30) < WINDOW_END:
            status = "cancelled"
            cancelled = _random_dt(rng, started + timedelta(days=30), WINDOW_END)
            cancelled_at = _stamp(cancelled)
        elif roll < 0.40:
            status = "past_due"
        else:
            status = "active"
        rows.append(
            {
                "subscription_id": f"sub_{number:05d}",
                "account_id": account["account_id"],
                "plan_id": plan_id,
                "status": status,
                "started_at": _stamp(started),
                "cancelled_at": cancelled_at,
            }
        )
    return rows


def _invoices(subscriptions: list[dict[str, str]], rng: random.Random) -> list[dict[str, object]]:
    price = {plan_id: cents for plan_id, _name, cents in PLANS}
    rows: list[dict[str, object]] = []
    for number in range(1, N_INVOICES + 1):
        subscription = subscriptions[rng.randrange(len(subscriptions))]
        started = datetime.strptime(subscription["started_at"], "%Y-%m-%d %H:%M:%S")
        if subscription["cancelled_at"]:
            period_end = datetime.strptime(subscription["cancelled_at"], "%Y-%m-%d %H:%M:%S")
        else:
            period_end = WINDOW_END
        if period_end <= started:
            period_end = started + timedelta(seconds=1)
        issued = _random_dt(rng, started, period_end)
        cents = price[subscription["plan_id"]]
        rows.append(
            {
                "invoice_id": f"inv_{number:06d}",
                "subscription_id": subscription["subscription_id"],
                "account_id": subscription["account_id"],
                "issued_at": _stamp(issued),
                "amount_eur": _money(cents),
                "status": "open",
                "_cents": cents,
            }
        )
    return rows


def _payment_rows(invoice: dict[str, object], parts: int, rng: random.Random) -> list[dict[str, str]]:
    cents = int(invoice["_cents"])
    if parts == 1:
        amounts = (cents,)
    else:
        first = cents // 2
        amounts = (first, cents - first)
    issued = datetime.strptime(str(invoice["issued_at"]), "%Y-%m-%d %H:%M:%S")
    latest = WINDOW_END - timedelta(seconds=1)
    paid_at = issued
    rows = []
    for amount in amounts:
        paid_at = min(paid_at + timedelta(days=rng.randrange(0, 8)), latest)
        method = METHODS[rng.randrange(len(METHODS))]
        if method == "card":
            card_last4 = f"{rng.randrange(10000):04d}"
        else:
            card_last4 = ""
        rows.append(
            {
                "payment_id": "",
                "invoice_id": str(invoice["invoice_id"]),
                "paid_at": _stamp(paid_at),
                "amount_eur": _money(amount),
                "method": method,
                "card_last4": card_last4,
            }
        )
    return rows


def _payments(invoices: list[dict[str, object]], rng: random.Random) -> list[dict[str, str]]:
    order = list(range(len(invoices)))
    rng.shuffle(order)
    one = order[:N_INVOICES_ONE_PAYMENT]
    two = order[N_INVOICES_ONE_PAYMENT : N_INVOICES_ONE_PAYMENT + N_INVOICES_TWO_PAYMENTS]
    rest = order[N_INVOICES_ONE_PAYMENT + N_INVOICES_TWO_PAYMENTS :]
    for index in rest[:N_VOID_INVOICES]:
        invoices[index]["status"] = "void"
    payments: list[dict[str, str]] = []
    for index in one:
        payments.extend(_payment_rows(invoices[index], 1, rng))
        invoices[index]["status"] = "paid"
    for index in two:
        payments.extend(_payment_rows(invoices[index], 2, rng))
        invoices[index]["status"] = "paid"
    for number, payment in enumerate(payments, start=1):
        payment["payment_id"] = f"pay_{number:06d}"
    return payments


def _check_rows(
    accounts: list[dict[str, str]],
    subscriptions: list[dict[str, str]],
    invoices: list[dict[str, object]],
    payments: list[dict[str, str]],
) -> None:
    if len(accounts) != N_ACCOUNTS or len(subscriptions) != N_SUBSCRIPTIONS:
        raise RuntimeError("account or subscription count drifted")
    if len(invoices) != N_INVOICES or len(payments) != N_PAYMENTS:
        raise RuntimeError("invoice or payment count drifted")
    statuses = Counter(str(row["status"]) for row in invoices)
    if set(statuses) != set(INVOICE_STATUSES):
        raise RuntimeError(f"invoice statuses were {sorted(statuses)}")
    sub_statuses = Counter(row["status"] for row in subscriptions)
    if set(sub_statuses) != set(SUBSCRIPTION_STATUSES):
        raise RuntimeError(f"subscription statuses were {sorted(sub_statuses)}")
    paid: dict[str, int] = {}
    for payment in payments:
        paid[payment["invoice_id"]] = paid.get(payment["invoice_id"], 0) + _parse_money(
            payment["amount_eur"]
        )
    for invoice in invoices:
        invoice_id = str(invoice["invoice_id"])
        got = paid.get(invoice_id, 0)
        if invoice["status"] == "paid":
            expected = _parse_money(str(invoice["amount_eur"]))
        else:
            expected = 0
        if got != expected:
            raise RuntimeError(f"{invoice_id} payments {got} != {expected}")


def _write(path: Path, columns: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in columns})


def write_csvs(raw_dir: Path | None = None) -> Path:
    """Write the five raw CSVs. Returns the directory."""
    _check_volumes()
    target = raw_dir or RAW_DIR
    rng, fake = _seeded()
    plans = _plans()
    accounts = _accounts(rng, fake)
    subscriptions = _subscriptions(accounts, rng)
    invoices = _invoices(subscriptions, rng)
    payments = _payments(invoices, rng)
    _check_rows(accounts, subscriptions, invoices, payments)
    tables = {
        "plans.csv": plans,
        "accounts.csv": accounts,
        "subscriptions.csv": subscriptions,
        "invoices.csv": invoices,
        "payments.csv": payments,
    }
    for name, columns in FILES.items():
        _write(target / name, columns, tables[name])
    return target


def main() -> None:
    raw_dir = write_csvs()
    for name in FILES:
        print(f"wrote {raw_dir / name}")


if __name__ == "__main__":
    main()
