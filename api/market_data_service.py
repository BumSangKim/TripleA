from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AssetUniverseItem:
    asset_code: str
    symbol: str
    name: str | None
    asset_class: str
    market: str | None
    currency: str
    source_type: str
    is_active: bool


@dataclass(frozen=True)
class AssetCoverage:
    asset_code: str
    currency: str
    price_start_date: date | None
    price_end_date: date | None
    price_points: int
    ok: bool
    message: str | None = None


@dataclass(frozen=True)
class FxCoverage:
    base_currency: str
    quote_currency: str
    rate_start_date: date | None
    rate_end_date: date | None
    rate_points: int
    ok: bool
    message: str | None = None


@dataclass(frozen=True)
class MarketDataCoverage:
    ok: bool
    assets: list[AssetCoverage]
    fx_rates: list[FxCoverage]

    @property
    def missing_messages(self) -> list[str]:
        return [
            item.message
            for item in [*self.assets, *self.fx_rates]
            if not item.ok and item.message
        ]


def get_asset_universe(
    conn: sqlite3.Connection,
    *,
    active_only: bool = True,
) -> list[AssetUniverseItem]:
    where = "WHERE COALESCE(is_active, 1) = 1" if active_only else ""
    rows = conn.execute(
        f"""
        SELECT asset_code, symbol, name, asset_class, market, currency, source_type, is_active
        FROM asset_universe
        {where}
        ORDER BY asset_class, asset_code
        """
    ).fetchall()
    return [_asset_from_row(row) for row in rows]


def resolve_asset_class_to_asset_code(
    conn: sqlite3.Connection,
    asset_class: str,
) -> str:
    row = conn.execute(
        """
        SELECT asset_code
        FROM asset_universe
        WHERE asset_class=?
          AND COALESCE(is_active, 1) = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        ((asset_class or "").strip(),),
    ).fetchone()
    if not row:
        raise KeyError(f"No backtest asset mapping for asset class: {asset_class}")
    return row["asset_code"]


def get_price_matrix(
    conn: sqlite3.Connection,
    asset_codes: list[str],
    start: date,
    end: date,
) -> dict[str, dict[date, float]]:
    codes = sorted({code for code in asset_codes if code})
    if not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"""
        SELECT asset_code, price_date, COALESCE(adj_close, close) AS price
        FROM market_prices
        WHERE asset_code IN ({placeholders})
          AND price_date BETWEEN ? AND ?
        ORDER BY asset_code, price_date
        """,
        [*codes, start.isoformat(), end.isoformat()],
    ).fetchall()
    matrix: dict[str, dict[date, float]] = {code: {} for code in codes}
    for row in rows:
        matrix[row["asset_code"]][_parse_date(row["price_date"])] = float(row["price"])
    return matrix


def get_fx_matrix(
    conn: sqlite3.Connection,
    base_currencies: list[str],
    start: date,
    end: date,
    *,
    quote_currency: str = "KRW",
) -> dict[str, dict[date, float]]:
    currencies = sorted({currency for currency in base_currencies if currency})
    matrix: dict[str, dict[date, float]] = {}
    for currency in currencies:
        if currency == quote_currency:
            matrix[currency] = {start: 1.0, end: 1.0}
            continue
        rows = conn.execute(
            """
            SELECT rate_date, rate
            FROM fx_rates
            WHERE base_currency=?
              AND quote_currency=?
              AND rate_date BETWEEN ? AND ?
            ORDER BY rate_date
            """,
            (currency, quote_currency, start.isoformat(), end.isoformat()),
        ).fetchall()
        matrix[currency] = {
            _parse_date(row["rate_date"]): float(row["rate"])
            for row in rows
        }
    return matrix


def validate_market_data_coverage(
    conn: sqlite3.Connection,
    asset_codes: list[str],
    start: date,
    end: date,
    *,
    base_currency: str = "KRW",
    max_stale_days: int = 7,
) -> MarketDataCoverage:
    if start > end:
        raise ValueError("start must be before or equal to end")

    universe = {
        item.asset_code: item
        for item in get_asset_universe(conn, active_only=False)
    }
    asset_results = [
        _validate_asset_coverage(conn, universe, asset_code, start, end, max_stale_days)
        for asset_code in sorted({code for code in asset_codes if code})
    ]
    fx_results = [
        _validate_fx_coverage(conn, currency, base_currency, start, end, max_stale_days)
        for currency in sorted({item.currency for item in asset_results if item.ok and item.currency != base_currency})
    ]
    ok = all(item.ok for item in [*asset_results, *fx_results])
    return MarketDataCoverage(ok=ok, assets=asset_results, fx_rates=fx_results)


def get_price_on_or_before(
    conn: sqlite3.Connection,
    asset_code: str,
    value_date: date,
) -> tuple[date, float]:
    row = conn.execute(
        """
        SELECT price_date, COALESCE(adj_close, close) AS price
        FROM market_prices
        WHERE asset_code=?
          AND price_date <= ?
        ORDER BY price_date DESC
        LIMIT 1
        """,
        (asset_code, value_date.isoformat()),
    ).fetchone()
    if not row:
        raise KeyError(f"No price for {asset_code} on or before {value_date.isoformat()}")
    return _parse_date(row["price_date"]), float(row["price"])


def get_fx_rate_on_or_before(
    conn: sqlite3.Connection,
    base_currency: str,
    value_date: date,
    *,
    quote_currency: str = "KRW",
) -> tuple[date, float]:
    if base_currency == quote_currency:
        return value_date, 1.0
    row = conn.execute(
        """
        SELECT rate_date, rate
        FROM fx_rates
        WHERE base_currency=?
          AND quote_currency=?
          AND rate_date <= ?
        ORDER BY rate_date DESC
        LIMIT 1
        """,
        (base_currency, quote_currency, value_date.isoformat()),
    ).fetchone()
    if not row:
        raise KeyError(
            f"No FX rate for {base_currency}/{quote_currency} on or before {value_date.isoformat()}"
        )
    return _parse_date(row["rate_date"]), float(row["rate"])


def _validate_asset_coverage(
    conn: sqlite3.Connection,
    universe: dict[str, AssetUniverseItem],
    asset_code: str,
    start: date,
    end: date,
    max_stale_days: int,
) -> AssetCoverage:
    asset = universe.get(asset_code)
    if not asset:
        return AssetCoverage(
            asset_code=asset_code,
            currency="",
            price_start_date=None,
            price_end_date=None,
            price_points=0,
            ok=False,
            message=f"{asset_code}: asset_universe mapping is missing",
        )
    if asset.source_type == "manual":
        return AssetCoverage(
            asset_code=asset.asset_code,
            currency=asset.currency,
            price_start_date=start,
            price_end_date=end,
            price_points=0,
            ok=True,
        )

    start_row = conn.execute(
        """
        SELECT price_date
        FROM market_prices
        WHERE asset_code=? AND price_date <= ?
        ORDER BY price_date DESC
        LIMIT 1
        """,
        (asset_code, start.isoformat()),
    ).fetchone()
    end_row = conn.execute(
        """
        SELECT price_date
        FROM market_prices
        WHERE asset_code=? AND price_date <= ?
        ORDER BY price_date DESC
        LIMIT 1
        """,
        (asset_code, end.isoformat()),
    ).fetchone()
    count_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM market_prices
        WHERE asset_code=?
          AND price_date BETWEEN ? AND ?
        """,
        (asset_code, start.isoformat(), end.isoformat()),
    ).fetchone()
    start_date = _parse_date(start_row["price_date"]) if start_row else None
    end_date = _parse_date(end_row["price_date"]) if end_row else None
    points = int(count_row["c"] or 0)

    ok = bool(start_date and end_date and points > 0)
    message = None
    if ok and start_date and (start - start_date).days > max_stale_days:
        ok = False
        message = f"{asset_code}: start price is stale ({start_date.isoformat()})"
    if ok and end_date and (end - end_date).days > max_stale_days:
        ok = False
        message = f"{asset_code}: end price is stale ({end_date.isoformat()})"
    if not ok and not message:
        message = f"{asset_code}: price data is missing for {start.isoformat()}..{end.isoformat()}"

    return AssetCoverage(
        asset_code=asset.asset_code,
        currency=asset.currency,
        price_start_date=start_date,
        price_end_date=end_date,
        price_points=points,
        ok=ok,
        message=message,
    )


def _validate_fx_coverage(
    conn: sqlite3.Connection,
    base_currency: str,
    quote_currency: str,
    start: date,
    end: date,
    max_stale_days: int,
) -> FxCoverage:
    start_row = conn.execute(
        """
        SELECT rate_date
        FROM fx_rates
        WHERE base_currency=? AND quote_currency=? AND rate_date <= ?
        ORDER BY rate_date DESC
        LIMIT 1
        """,
        (base_currency, quote_currency, start.isoformat()),
    ).fetchone()
    end_row = conn.execute(
        """
        SELECT rate_date
        FROM fx_rates
        WHERE base_currency=? AND quote_currency=? AND rate_date <= ?
        ORDER BY rate_date DESC
        LIMIT 1
        """,
        (base_currency, quote_currency, end.isoformat()),
    ).fetchone()
    count_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM fx_rates
        WHERE base_currency=?
          AND quote_currency=?
          AND rate_date BETWEEN ? AND ?
        """,
        (base_currency, quote_currency, start.isoformat(), end.isoformat()),
    ).fetchone()
    start_date = _parse_date(start_row["rate_date"]) if start_row else None
    end_date = _parse_date(end_row["rate_date"]) if end_row else None
    points = int(count_row["c"] or 0)

    ok = bool(start_date and end_date and points > 0)
    message = None
    if ok and start_date and (start - start_date).days > max_stale_days:
        ok = False
        message = f"{base_currency}/{quote_currency}: start FX rate is stale ({start_date.isoformat()})"
    if ok and end_date and (end - end_date).days > max_stale_days:
        ok = False
        message = f"{base_currency}/{quote_currency}: end FX rate is stale ({end_date.isoformat()})"
    if not ok and not message:
        message = f"{base_currency}/{quote_currency}: FX data is missing for {start.isoformat()}..{end.isoformat()}"

    return FxCoverage(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_start_date=start_date,
        rate_end_date=end_date,
        rate_points=points,
        ok=ok,
        message=message,
    )


def _asset_from_row(row: sqlite3.Row) -> AssetUniverseItem:
    return AssetUniverseItem(
        asset_code=row["asset_code"],
        symbol=row["symbol"],
        name=row["name"],
        asset_class=row["asset_class"],
        market=row["market"],
        currency=row["currency"],
        source_type=row["source_type"],
        is_active=bool(row["is_active"]),
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])
