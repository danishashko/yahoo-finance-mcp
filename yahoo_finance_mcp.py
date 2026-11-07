#!/usr/bin/env python3
"""
Yahoo Finance MCP Server

This MCP server provides tools to access financial market data from Yahoo Finance,
including stock prices, company information, financial statements, and market analysis.

Built with the MCP Python SDK (MCPServer) and yfinance.
"""

import argparse
import functools
import inspect
import json
import logging
import math
import re
from enum import Enum
from typing import Annotated, Any, Dict, List

import yfinance as yf
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent

# Keep yfinance from emitting warnings/progress that could clutter the
# stderr stream of an MCP stdio server. The JSON-RPC channel is stdout only.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

__version__ = "1.6.1"

# Initialize the MCP server
mcp = MCPServer(
    "yahoo_finance_mcp",
    version=__version__,
    instructions=(
        "Read-only Yahoo Finance market data: no account, no API key, nothing is written. "
        "Start with search_symbols when you have a company name but no ticker. "
        "Per stock: get_stock_quote (price), get_company_info (profile), get_financial_statements, "
        "get_analyst_recommendations, get_analyst_estimates, get_earnings (next date, beat/miss history), "
        "get_holders (institutions, insider trades, insider net buying), get_dividends_splits, "
        "get_options_chain, get_market_news. Funds: get_fund_data. "
        "Discovery: screen_stocks (movers, most active, undervalued), get_earnings_calendar (who reports when), "
        "get_sector_overview (sector and industry leaders). Market-wide: get_market_status, compare_stocks. "
        "Every tool takes response_format='json' for machine-readable output. Data can be delayed about 15 "
        "minutes and Yahoo rate-limits bursts: space out large batches. Not investment advice."
    ),
)

# Constants
CHARACTER_LIMIT = 25000  # Maximum response size in characters


# ============================================================================
# SHARED HTTP SESSION
# ============================================================================
#
# Yahoo Finance aggressively rate-limits plain HTTP clients (HTTP 429 /
# YFRateLimitError). The community-proven mitigation is a single curl_cffi
# session with browser impersonation, reused across every Ticker call so the
# crumb/cookie handshake happens once. We build it lazily and degrade
# gracefully to yfinance's default session if curl_cffi is unavailable.

_SESSION = None
_SESSION_TRIED = False


def _get_session():
    """Return a shared curl_cffi session, or None to use yfinance's default."""
    global _SESSION, _SESSION_TRIED
    if _SESSION_TRIED:
        return _SESSION
    _SESSION_TRIED = True
    try:
        from curl_cffi import requests as _creq

        # Safari, not Chrome: on curl_cffi 0.17 (which yfinance 1.8 requires) the
        # chrome and firefox profiles stall the first request on every new thread
        # for seconds, against any host, so a burst of parallel calls queued up
        # for ~8s. safari and edge do not (measured 2026-11-06, 8 threads: chrome
        # 7.7s, safari 0.56s). Re-measure before switching back.
        _SESSION = _creq.Session(impersonate="safari")
    except Exception:
        _SESSION = None  # fall back to yfinance's built-in session
    return _SESSION


def make_ticker(symbol: str) -> "yf.Ticker":
    """Create a yfinance Ticker bound to the shared session when available."""
    session = _get_session()
    if session is not None:
        try:
            return yf.Ticker(symbol, session=session)
        except Exception:
            pass
    return yf.Ticker(symbol)


# ============================================================================
# ENUMS
# ============================================================================


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


class Period(str, Enum):
    """Time periods for historical data."""

    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"
    SIX_MONTHS = "6mo"
    ONE_YEAR = "1y"
    TWO_YEARS = "2y"
    FIVE_YEARS = "5y"
    TEN_YEARS = "10y"
    YTD = "ytd"
    MAX = "max"


class Interval(str, Enum):
    """Data intervals for historical prices."""

    ONE_MINUTE = "1m"
    TWO_MINUTES = "2m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    SIXTY_MINUTES = "60m"
    NINETY_MINUTES = "90m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"


class OptionType(str, Enum):
    """Which side of the options chain to return."""

    CALLS = "calls"
    PUTS = "puts"
    BOTH = "both"


class MarketRegion(str, Enum):
    """Markets yfinance's Market() accepts."""

    US = "US"
    GB = "GB"
    ASIA = "ASIA"
    EUROPE = "EUROPE"
    RATES = "RATES"
    COMMODITIES = "COMMODITIES"
    CURRENCIES = "CURRENCIES"
    CRYPTOCURRENCIES = "CRYPTOCURRENCIES"


class HolderType(str, Enum):
    """Category of ownership data."""

    INSTITUTIONAL = "institutional"
    MUTUALFUND = "mutualfund"
    MAJOR = "major"
    INSIDER_TRANSACTIONS = "insider_transactions"
    INSIDER_PURCHASES = "insider_purchases"
    INSIDER_ROSTER = "insider_roster"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


_CLASS_SHARE = re.compile(r"^([A-Z]{1,5})[./]([A-C])$")


def _norm_ticker(value: str) -> str:
    """Normalize a ticker to Yahoo's spelling.

    Class shares are written BRK.B or BRK/B almost everywhere else, but Yahoo
    spells them BRK-B and answers BRK.B with an empty quote. Only a single
    A-C letter after the separator is rewritten: Yahoo's own exchange suffixes
    (BP.L, 7203.T, SAP.DE) never use those letters, so they pass through.
    """
    value = value.strip().upper()
    return _CLASS_SHARE.sub(r"\1-\2", value)


def _unknown_symbol(ticker: str) -> ToolError:
    return ToolError(
        f"Unknown symbol '{ticker}'. Yahoo Finance has no quote for it. Use search_symbols "
        "to find the right ticker; non-US listings need an exchange suffix (e.g. 7203.T, BP.L)."
    )


def _require_known(info: Dict[str, Any], ticker: str) -> None:
    """Refuse a symbol Yahoo does not know instead of answering with N/A fields.

    yfinance does not raise for an unknown symbol: `.info` comes back as a
    near-empty dict and every field renders as N/A, so the call used to succeed
    with nothing in it and an agent had no signal that the ticker was wrong.
    """
    has_name = info.get("shortName") or info.get("longName")
    has_price = (
        info.get("regularMarketPrice") is not None
        or info.get("currentPrice") is not None
    )
    if not has_name and not has_price:
        raise _unknown_symbol(ticker)


def _error(what: str, ticker: str, exc: Exception) -> ToolError:
    """Turn a failure into a ToolError, so the client gets is_error=True.

    Returned errors used to be ordinary text, indistinguishable from a real
    answer unless the caller read the wording. Raising ToolError marks the
    result as an error and still carries the message. Detects Yahoo
    rate-limiting and gives specific guidance for it.
    """
    if isinstance(exc, ToolError):
        raise exc
    raise ToolError(_error_text(what, ticker, exc)) from exc


def _error_text(what: str, ticker: str, exc: Exception) -> str:
    name = type(exc).__name__
    if "RateLimit" in name or "Too Many Requests" in str(exc):
        return (
            f"Yahoo Finance is rate-limiting requests right now (fetching {what} for {ticker}).\n\n"
            "**Troubleshooting:**\n"
            "- Wait a minute and try again\n"
            "- Avoid making many requests in quick succession"
        )
    msg = f"Error fetching {what} for {ticker}: {str(exc)}\n\n"
    msg += "**Troubleshooting:**\n"
    msg += "- Verify the ticker symbol is correct\n"
    msg += f"- {what.capitalize()} may not be available for this symbol"
    return msg


def _iso_time(info: Dict[str, Any]) -> Any:
    """The quote's regularMarketTime as ISO 8601 in the exchange's timezone."""
    ts = info.get("regularMarketTime")
    if not isinstance(ts, (int, float)):
        return None
    t = pd.Timestamp(ts, unit="s", tz="UTC")
    tz = info.get("exchangeTimezoneName")
    if tz:
        try:
            t = t.tz_convert(tz)
        except Exception:
            pass
    return t.isoformat()


def _market_line(info: Dict[str, Any]) -> str:
    """'Tokyo, JPY, market CLOSED, as of 2026-11-06T15:30:00+09:00'."""
    parts = [
        info.get("fullExchangeName") or info.get("exchange"),
        info.get("currency"),
        f"market {info['marketState']}" if info.get("marketState") else None,
        f"as of {_iso_time(info)}" if _iso_time(info) else None,
    ]
    return ", ".join(x for x in parts if x) or "N/A"


def safe_get(data: Dict[str, Any], key: str, default: Any = "N/A") -> Any:
    """Safely get a value from a dictionary."""
    return data.get(key, default)


def format_currency(value: Any, currency: str = "USD") -> str:
    """Format a value as currency: $ for USD, otherwise the ISO code after it."""
    if value is None or value == "N/A":
        return "N/A"
    try:
        if currency and currency != "USD":
            return f"{value:,.2f} {currency}"
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return str(value)


def format_large_number(value: Any) -> str:
    """Format large numbers with K, M, B suffixes."""
    if value is None or value == "N/A":
        return "N/A"
    try:
        num = float(value)
        if abs(num) >= 1e9:
            return f"${num / 1e9:.2f}B"
        elif abs(num) >= 1e6:
            return f"${num / 1e6:.2f}M"
        elif abs(num) >= 1e3:
            return f"${num / 1e3:.2f}K"
        else:
            return f"${num:.2f}"
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: Any) -> str:
    """Format a fractional value (e.g. 0.25) as a percentage (25.00%)."""
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{float(value) * 100:.2f}%"
    except (ValueError, TypeError):
        return str(value)


def format_dividend_yield(value: Any) -> str:
    """Format a dividend yield.

    Modern yfinance returns ``dividendYield`` already expressed as a percentage
    number (e.g. ``0.35`` means 0.35%, ``3.10`` means 3.10%), so it must NOT be
    multiplied by 100 the way fractional fields are.
    """
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return str(value)


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Convert a pandas DataFrame to markdown.

    Falls back to a plain-text table if the optional ``tabulate`` package is
    unavailable, so a missing dependency never breaks a tool.
    """
    if df is None or df.empty:
        return "No data available"

    truncated_msg = ""
    if len(df) > max_rows:
        total = len(df)
        df = df.head(max_rows)
        truncated_msg = f"\n\n*Showing first {max_rows} rows of {total} total*"

    try:
        return df.to_markdown() + truncated_msg
    except ImportError:
        # tabulate not installed - degrade gracefully to a fenced plain table.
        return "```\n" + df.to_string() + "\n```" + truncated_msg


def _finite(value: Any) -> Any:
    """Replace every non-finite float with None, recursively.

    Python writes `NaN`, `Infinity` and `-Infinity` bare, and none of the three
    is valid JSON - `JSON.parse` refuses the whole document. yfinance returns
    NaN for any figure a source did not supply (`get_analyst_estimates` hits it
    on the LTG growth row for most tickers), so without this a successful call
    hands the client a payload it cannot read, with every HTTP status saying
    the call worked. Serialising them as null loses nothing: the field was
    missing either way.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str) and value == "N/A":
        return None  # the Markdown placeholder; JSON says missing with null
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


def _json(payload: Any) -> str:
    """Serialise to strictly valid JSON, with non-finite floats as null.

    `allow_nan=False` is the backstop: if a non-finite value ever arrives in a
    type `_finite` does not walk, this raises inside the tool's own try/except
    and the caller gets a readable error, rather than a green node holding
    unparseable text.
    """
    return json.dumps(_finite(payload), indent=2, default=str, allow_nan=False)


def _statement_to_dict(df: Any, max_rows: int = 30) -> Dict[str, Any]:
    """A financial statement keyed by period, with the periods as strings.

    Every column label on these frames is a pandas Timestamp, and `to_dict()`
    makes those labels the keys of the returned mapping. `json.dumps` only
    coerces *values* through `default=`, never keys, so serialising the frame
    raised "keys must be str, int, float, bool or None, not Timestamp" and the
    whole tool answered with an error string - in JSON mode only, while the
    markdown branch rendered the same frame fine.
    """
    if df is None or getattr(df, "empty", True):
        return {}
    out = df.copy()
    out.columns = [
        c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)
        for c in out.columns
    ]
    # Same 30-row cap the markdown branch applies per statement. All three
    # uncapped come to ~38,800 characters for NVDA against a 25,000 limit, and
    # an oversized JSON payload is refused rather than trimmed, so leaving them
    # whole cost the caller all three statements instead of the tail of each.
    if len(out) > max_rows:
        out = out.head(max_rows)
    return out.to_dict()


def _fit_records(
    records: List[Any],
    envelope: Dict[str, Any],
    key: str,
    hint: str = "Narrow the period or widen the interval for full coverage.",
    newest_first: bool = False,
) -> str:
    """Serialise as many of the newest records as the response limit allows.

    The JSON branch refuses an oversized payload outright rather than trimming
    it, so an uncapped frame does not come back shortened - it does not come
    back at all. A year of daily bars is about 65,000 characters, so asking for
    a year silently returned nothing. Keep the tail, and say what was dropped.
    """
    kept = len(records)
    while True:
        body = dict(envelope)
        kept_rows = records[len(records) - kept :] if kept else []
        body[key] = kept_rows[::-1] if newest_first else kept_rows
        body["returnedRecords"] = kept
        body["truncated"] = kept < len(records)
        if body["truncated"]:
            body["note"] = f"Newest {kept} of {len(records)} records. {hint}"
        payload = _json(body)
        if len(payload) <= CHARACTER_LIMIT or kept == 0:
            return payload
        kept = kept * 3 // 4 if kept > 4 else kept - 1


def truncate_response(response: str, message: str = "") -> str:
    """Truncate a (markdown/text) response if it exceeds CHARACTER_LIMIT."""
    if len(response) <= CHARACTER_LIMIT:
        return response

    suffix = (
        f"\n\n⚠️ Response truncated at {CHARACTER_LIMIT} characters. {message}".rstrip()
    )
    # Reserve room for the suffix so the total never exceeds CHARACTER_LIMIT.
    return response[: max(0, CHARACTER_LIMIT - len(suffix))] + suffix


def truncate_json_response(payload: str, message: str = "") -> str:
    """Cap an oversized JSON payload without dumping it into context.

    Returns a small, valid-JSON message asking the caller to narrow the request
    rather than a giant mid-cut preview (which is both context-bloating and
    useless to the model). Keeps the total response tiny.
    """
    if len(payload) <= CHARACTER_LIMIT:
        return payload

    note = (
        f"Response was too large (~{len(payload)} characters) and was not returned in full. "
        f"{message}".strip()
    )
    raise _TooLarge(note)


# ============================================================================
# STRUCTURED OUTPUT
# ============================================================================
#
# Every tool returns two things: text for the model to read (Markdown, or JSON
# when response_format='json') and the same data as `structuredContent`, typed
# by the tool's published `outputSchema`. A client that understands structured
# output reads fields directly; one that does not reads the text as before.
#
# The schemas are published but not enforced at call time: a field Yahoo
# returns in an unexpected type must not turn a good answer into an error.
# The release checks validate every tool's structuredContent against its
# schema instead (see AGENTS.md).


class _TooLarge(Exception):
    """A JSON payload over CHARACTER_LIMIT."""


class _Out(BaseModel):
    """Fields every tool's structured output may carry."""

    model_config = ConfigDict(extra="allow")
    message: str | None = Field(
        None,
        description="Set instead of data when there is nothing to return for this request (for example, no dividends on record).",
    )


class _Row(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


Num = float | None
Str = str | None


class QuoteOut(_Out):
    ticker: Str = None
    longName: Str = None
    currency: Str = Field(
        None,
        description="ISO currency of every price field, e.g. USD, JPY, GBp (pence).",
    )
    exchange: Str = None
    marketState: Str = Field(
        None, description="PRE, REGULAR, POST, CLOSED and similar."
    )
    regularMarketTime: Str = Field(
        None,
        description="ISO 8601 time of the last regular-session price, in the exchange's timezone.",
    )
    quoteType: Str = None
    currentPrice: Num = None
    previousClose: Num = None
    change: Num = None
    changePercent: Num = None
    open: Num = None
    dayLow: Num = None
    dayHigh: Num = None
    fiftyTwoWeekLow: Num = None
    fiftyTwoWeekHigh: Num = None
    volume: Num = None
    averageVolume: Num = None
    marketCap: Num = None
    beta: Num = None
    trailingPE: Num = None
    trailingEps: Num = None
    dividendYield: Num = Field(None, description="Percent, e.g. 0.41 means 0.41%.")
    sector: Str = None
    industry: Str = None
    website: Str = None


class PriceBar(_Row):
    Date: Str = None
    Open: Num = None
    High: Num = None
    Low: Num = None
    Close: Num = None
    Volume: Num = None
    Dividends: Num = None
    Stock_Splits: Num = Field(None, alias="Stock Splits")


class HistoryOut(_Out):
    ticker: Str = None
    period: Str = None
    interval: Str = None
    totalRecords: int | None = None
    returnedRecords: int | None = None
    truncated: bool | None = Field(
        None, description="True when only the newest records fit the response limit."
    )
    note: Str = None
    data: list[PriceBar] | None = None


class CompanyInfoOut(_Out):
    """Yahoo's full company profile; the listed fields are the most used of ~180."""

    symbol: Str = None
    longName: Str = None
    currency: Str = None
    sector: Str = None
    industry: Str = None
    country: Str = None
    website: Str = None
    longBusinessSummary: Str = None
    fullTimeEmployees: Num = None
    marketCap: Num = None
    enterpriseValue: Num = None
    trailingPE: Num = None
    forwardPE: Num = None
    priceToBook: Num = None
    profitMargins: Num = None
    revenueGrowth: Num = None
    totalRevenue: Num = None
    totalCash: Num = None
    totalDebt: Num = None
    freeCashflow: Num = None
    companyOfficers: list[dict[str, Any]] | None = None


class StatementsOut(_Out):
    ticker: Str = None
    incomeStatement: dict[str, dict[str, Num]] | None = Field(
        None, description="Period end date -> line item -> value."
    )
    balanceSheet: dict[str, dict[str, Num]] | None = None
    cashFlow: dict[str, dict[str, Num]] | None = None
    lineItemCounts: dict[str, int] | None = None


class CompareRow(_Row):
    Ticker: Str = None
    Name: Str = None
    Currency: Str = None
    Price: Num = None
    Change_pct: Num = Field(None, alias="Change%")
    MarketCap: Num = None
    PE: Num = None
    EPS: Num = None
    DivYield_pct: Num = Field(None, alias="DivYield%")
    Beta: Num = None
    High52w: Num = Field(None, alias="52WkHigh")
    Low52w: Num = Field(None, alias="52WkLow")
    Volume: Num = None
    AvgVolume: Num = None
    Sector: Str = None
    Industry: Str = None
    Error: Str = Field(None, description="Set when this ticker could not be fetched.")


class CompareOut(_Out):
    tickers: list[str] | None = None
    comparison: list[CompareRow] | None = None


class RecommendationsOut(_Out):
    ticker: Str = None
    priceTargets: dict[str, Num] | None = None
    consensus: dict[str, Any] | None = None
    recommendationTrend: list[dict[str, Any]] | None = None
    upgradesDowngrades: list[dict[str, Any]] | None = None


class NewsItem(_Row):
    title: Str = None
    provider: Str = None
    pubDate: Str = None
    summary: Str = None
    url: Str = None
    tickers: list[str] | None = Field(
        None, description="Tickers Yahoo tagged the story with, lead ticker first."
    )
    primarilyAbout: bool | None = Field(
        None, description="True when the story is led by the requested ticker."
    )


class NewsOut(_Out):
    ticker: Str = None
    count: int | None = None
    news: list[NewsItem] | None = None


class OptionsOut(_Out):
    ticker: Str = None
    expirationDates: list[str] | None = Field(
        None, description="Present when no expiration_date was given."
    )
    expirationDate: Str = None
    underlyingPrice: Num = None
    strikesPerSide: int | None = None
    truncated: bool | None = Field(
        None, description="True when only the strikes nearest the underlying price fit."
    )
    note: Str = None
    calls: list[dict[str, Any]] | None = None
    puts: list[dict[str, Any]] | None = None


class HoldersOut(_Out):
    ticker: Str = None
    holderType: Str = None
    data: list[dict[str, Any]] | None = Field(
        None,
        description="One row per holder or transaction; columns depend on holderType.",
    )
    returnedRecords: int | None = None
    truncated: bool | None = None
    note: Str = None


class DividendsOut(_Out):
    ticker: Str = None
    dividends: list[dict[str, Any]] | None = Field(
        None, description="{date, amount} per payment."
    )
    splits: list[dict[str, Any]] | None = Field(
        None, description="{date, ratio} per split."
    )


class EstimatesOut(_Out):
    ticker: Str = None
    priceTargets: dict[str, Num] | None = None
    earningsEstimate: list[dict[str, Any]] | None = None
    revenueEstimate: list[dict[str, Any]] | None = None
    growthEstimates: list[dict[str, Any]] | None = None


class SymbolMatch(_Row):
    symbol: Str = None
    name: Str = None
    exchange: Str = None
    type: Str = None
    sector: Str = None
    industry: Str = None


class SearchOut(_Out):
    query: Str = None
    count: int | None = None
    results: list[SymbolMatch] | None = None


class MarketStatusOut(_Out):
    region: Str = None
    status: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


class EarningsOut(_Out):
    ticker: Str = None
    nextEarningsDate: Str = None
    nextEarningsWindow: list[str] | None = None
    daysUntilEarnings: int | None = None
    epsEstimate: dict[str, Num] | None = None
    revenueEstimate: dict[str, Num] | None = None
    exDividendDate: Str = None
    beats: int | None = None
    reportsWithSurprise: int | None = None
    history: list[dict[str, Any]] | None = Field(
        None,
        description="{date, epsEstimate, reportedEps, surprisePercent} per report.",
    )


class EarningsCalendarRow(_Row):
    symbol: Str = None
    company: Str = None
    marketCap: Num = None
    event: Str = None
    date: Str = None
    timing: Str = Field(
        None,
        description="BMO (before open), AMC (after close) or TNS (time not supplied).",
    )
    epsEstimate: Num = None
    reportedEps: Num = None
    surprisePercent: Num = None


class EarningsCalendarOut(_Out):
    start: Str = None
    end: Str = None
    count: int | None = None
    earnings: list[EarningsCalendarRow] | None = None


class ScreenRow(_Row):
    symbol: Str = None
    name: Str = None
    type: Str = None
    price: Num = None
    changePercent: Num = None
    volume: Num = None
    relativeVolume: Num = Field(
        None, description="Today's volume divided by the 3-month average."
    )
    marketCap: Num = None
    trailingPE: Num = None
    forwardPE: Num = None
    fiftyTwoWeekLow: Num = None
    fiftyTwoWeekHigh: Num = None
    exchange: Str = None


class ScreenOut(_Out):
    screener: Str = None
    title: Str = None
    total: int | None = None
    count: int | None = None
    results: list[ScreenRow] | None = None


class FundOut(_Out):
    ticker: Str = None
    overview: dict[str, Any] | None = None
    description: Str = None
    operations: dict[str, dict[str, Num]] | None = Field(
        None, description="Attribute -> {fund, categoryAverage}."
    )
    topHoldings: list[dict[str, Any]] | None = Field(
        None, description="{symbol, name, weight} with weight as a fraction."
    )
    sectorWeightings: dict[str, Num] | None = None
    assetClasses: dict[str, Num] | None = None


class SectorOut(_Out):
    sector: Str = None
    industry: Str = None
    name: Str = None
    overview: dict[str, Any] | None = None
    topCompanies: list[dict[str, Any]] | None = None
    industries: list[dict[str, Any]] | None = Field(
        None,
        description="Present for a sector; each row's key is a valid industry argument.",
    )
    topGrowthCompanies: list[dict[str, Any]] | None = None
    topPerformingCompanies: list[dict[str, Any]] | None = None


_OUTPUT_MODELS: Dict[str, type[_Out]] = {}


def structured(model: type[_Out]):
    """Register a tool's output model and turn a plain-text return into a result.

    A tool returns either a finished CallToolResult (from _respond) or a short
    string such as "No dividend history available", which becomes the text and
    `{"message": ...}` as structured content.
    """

    def wrap(fn):
        _OUTPUT_MODELS[fn.__name__] = model

        @functools.wraps(fn)
        def run(*args, **kwargs):
            result = fn(*args, **kwargs)
            if isinstance(result, CallToolResult):
                return result
            text = str(result)
            return CallToolResult(
                content=[TextContent(type="text", text=text)],
                structured_content={"message": text},
            )

        run.__signature__ = inspect.signature(fn).replace(
            return_annotation=CallToolResult
        )
        run.__annotations__ = {**fn.__annotations__, "return": CallToolResult}
        return run

    return wrap


def _respond(fmt: "ResponseFormat", md, js) -> CallToolResult:
    """Build the text in the requested format plus the structured copy.

    The JSON payload is always built: it is the structured content. When it is
    over the response limit, a JSON request fails with a ToolError naming the
    fix, and a Markdown request still gets its text with a short message as
    the structured part.
    """
    try:
        json_text = js()
        structured_content = json.loads(json_text)
        if not isinstance(structured_content, dict):
            structured_content = {"data": structured_content}
    except _TooLarge as exc:
        if fmt != ResponseFormat.MARKDOWN:
            raise ToolError(str(exc)) from exc
        json_text, structured_content = None, {"message": str(exc)}
    text = md() if fmt == ResponseFormat.MARKDOWN else json_text
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=structured_content,
    )


def _publish_output_schemas() -> None:
    """Attach each tool's output schema. The SDK reads it live on tools/list."""
    for name, model in _OUTPUT_MODELS.items():
        tool = mcp._tool_manager.get_tool(name)
        tool.fn_metadata.output_schema = model.model_json_schema(by_alias=True)


# ============================================================================
# MCP TOOLS
# ============================================================================


@mcp.tool(
    structured_output=False,
    name="get_stock_quote",
    annotations={
        "title": "Get Current Stock Quote",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(QuoteOut)
def get_stock_quote(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL' for Apple, 'MSFT' for Microsoft, 'TSLA' for Tesla)",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Real-time quote snapshot for ONE stock: last price, day change ($ and %), open, previous close, day range, 52-week range, volume and average volume, market cap, beta, trailing P/E, EPS, dividend yield, and sector/industry/website.

    Use for "what's the price of X" or a quick single-stock snapshot. For several stocks side by side use compare_stocks; for the full company profile use get_company_info; for a past price series use get_historical_prices.

    Returns Markdown by default, or structured JSON when response_format='json'. An unknown ticker or an upstream/rate-limit error returns a short error message rather than raising.
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = make_ticker(ticker)
        info = ticker_obj.info
        _require_known(info, ticker)
        cur = info.get("currency") or "USD"

        # Get fast info for real-time data
        try:
            fast_info = ticker_obj.fast_info
            current_price = fast_info.get("lastPrice", safe_get(info, "currentPrice"))
            previous_close = fast_info.get(
                "previousClose", safe_get(info, "previousClose")
            )
        except Exception:
            current_price = safe_get(info, "currentPrice")
            previous_close = safe_get(info, "previousClose")

        # Calculate change
        if current_price != "N/A" and previous_close != "N/A":
            try:
                change = current_price - previous_close
                change_pct = (change / previous_close) * 100
            except (TypeError, ZeroDivisionError):
                change = "N/A"
                change_pct = "N/A"
        else:
            change = "N/A"
            change_pct = "N/A"

        def _md():
            result = f"# {safe_get(info, 'longName', ticker)} ({ticker})\n\n"
            result += f"**Current Price:** {format_currency(current_price, cur)}\n"
            result += f"**Market:** {_market_line(info)}\n"

            if change != "N/A":
                change_symbol = "🔺" if change >= 0 else "🔻"
                result += f"**Change:** {change_symbol} {format_currency(change, cur)} ({change_pct:.2f}%)\n"

            result += "\n## Market Data\n"
            result += f"- **Previous Close:** {format_currency(previous_close, cur)}\n"
            result += f"- **Open:** {format_currency(safe_get(info, 'open'), cur)}\n"
            result += f"- **Day's Range:** {format_currency(safe_get(info, 'dayLow'), cur)} - {format_currency(safe_get(info, 'dayHigh'), cur)}\n"
            result += f"- **52 Week Range:** {format_currency(safe_get(info, 'fiftyTwoWeekLow'), cur)} - {format_currency(safe_get(info, 'fiftyTwoWeekHigh'), cur)}\n"
            result += (
                f"- **Volume:** {safe_get(info, 'volume'):,}\n"
                if safe_get(info, "volume") != "N/A"
                else "- **Volume:** N/A\n"
            )
            result += (
                f"- **Avg Volume:** {safe_get(info, 'averageVolume'):,}\n"
                if safe_get(info, "averageVolume") != "N/A"
                else "- **Avg Volume:** N/A\n"
            )
            result += f"- **Market Cap:** {format_large_number(safe_get(info, 'marketCap'))}\n"
            result += f"- **Beta:** {safe_get(info, 'beta')}\n"
            result += f"- **PE Ratio:** {safe_get(info, 'trailingPE')}\n"
            result += (
                f"- **EPS:** {format_currency(safe_get(info, 'trailingEps'), cur)}\n"
            )
            result += f"- **Dividend Yield:** {format_dividend_yield(safe_get(info, 'dividendYield'))}\n"

            result += "\n## Company Info\n"
            result += f"- **Sector:** {safe_get(info, 'sector')}\n"
            result += f"- **Industry:** {safe_get(info, 'industry')}\n"
            result += f"- **Website:** {safe_get(info, 'website')}\n"

            return truncate_response(
                result, "Use get_company_info for more detailed information."
            )

        def _js():
            result = {
                "ticker": ticker,
                "longName": safe_get(info, "longName"),
                "currency": info.get("currency"),
                "exchange": info.get("fullExchangeName") or info.get("exchange"),
                "marketState": info.get("marketState"),
                "regularMarketTime": _iso_time(info),
                "quoteType": info.get("quoteType"),
                "currentPrice": current_price,
                "previousClose": previous_close,
                "change": change,
                "changePercent": change_pct,
                "open": safe_get(info, "open"),
                "dayLow": safe_get(info, "dayLow"),
                "dayHigh": safe_get(info, "dayHigh"),
                "fiftyTwoWeekLow": safe_get(info, "fiftyTwoWeekLow"),
                "fiftyTwoWeekHigh": safe_get(info, "fiftyTwoWeekHigh"),
                "volume": safe_get(info, "volume"),
                "averageVolume": safe_get(info, "averageVolume"),
                "marketCap": safe_get(info, "marketCap"),
                "beta": safe_get(info, "beta"),
                "trailingPE": safe_get(info, "trailingPE"),
                "trailingEps": safe_get(info, "trailingEps"),
                "dividendYield": safe_get(info, "dividendYield"),
                "sector": safe_get(info, "sector"),
                "industry": safe_get(info, "industry"),
                "website": safe_get(info, "website"),
            }
            return _json(result)

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("quote", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_historical_prices",
    annotations={
        "title": "Get Historical Stock Prices",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(HistoryOut)
def get_historical_prices(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')",
            min_length=1,
            max_length=10,
        ),
    ],
    period: Annotated[
        Period,
        Field(
            description="Time period for historical data (e.g., '1mo' for 1 month, '1y' for 1 year)"
        ),
    ] = Period.ONE_MONTH,
    interval: Annotated[
        Interval,
        Field(description="Data interval (e.g., '1d' for daily, '1h' for hourly)"),
    ] = Interval.ONE_DAY,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Historical OHLCV price series for one stock over a chosen period/interval, plus summary stats (highest/lowest/average close, average volume) and total return over the window.

    Use for performance, trends, or charting ("how has X done over the last year"). For a single current price use get_stock_quote; for dividend/split events use get_dividends_splits. Note: intraday intervals (1m-90m) are only available for short recent periods, and long periods return many rows, so prefer JSON or a shorter period if the output is truncated.

    Returns Markdown (summary stats plus the last 10 rows) by default, or the full series as JSON when response_format='json'. An empty or unsupported period/interval combination returns a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = make_ticker(ticker)
        hist = ticker_obj.history(period=period.value, interval=interval.value)

        if hist.empty:
            return f"No historical data available for {ticker} with period={period.value} and interval={interval.value}"

        def _md():
            result = f"# Historical Prices: {ticker}\n\n"
            result += f"**Period:** {period.value} | **Interval:** {interval.value}\n\n"
            result += f"**Date Range:** {hist.index[0].strftime('%Y-%m-%d')} to {hist.index[-1].strftime('%Y-%m-%d')}\n"
            result += f"**Total Records:** {len(hist)}\n\n"

            result += "## Summary Statistics\n\n"
            result += f"- **Highest Close:** {format_currency(hist['Close'].max())} on {hist['Close'].idxmax().strftime('%Y-%m-%d')}\n"
            result += f"- **Lowest Close:** {format_currency(hist['Close'].min())} on {hist['Close'].idxmin().strftime('%Y-%m-%d')}\n"
            result += f"- **Average Close:** {format_currency(hist['Close'].mean())}\n"
            result += f"- **Average Volume:** {hist['Volume'].mean():,.0f}\n"

            if len(hist) > 1:
                start_price = hist["Close"].iloc[0]
                end_price = hist["Close"].iloc[-1]
                total_return = ((end_price - start_price) / start_price) * 100
                result += f"- **Total Return:** {total_return:.2f}%\n"

            result += "\n## Recent Data\n\n"
            recent_data = hist.tail(10).copy()
            recent_data.index = recent_data.index.strftime("%Y-%m-%d %H:%M")
            result += dataframe_to_markdown(recent_data)

            if len(hist) > 10:
                result += f"\n\n*Showing last 10 of {len(hist)} records. JSON format returns as many of the newest records as fit in one response.*"

            return truncate_response(
                result,
                "Request smaller time period or use JSON format for complete data.",
            )

        def _js():
            hist_dict = hist.reset_index().to_dict(orient="records")
            for record in hist_dict:
                if "Date" in record:
                    record["Date"] = record["Date"].isoformat()
                elif "Datetime" in record:
                    record["Datetime"] = record["Datetime"].isoformat()

            return _fit_records(
                hist_dict,
                {
                    "ticker": ticker,
                    "period": period.value,
                    "interval": interval.value,
                    "totalRecords": len(hist),
                },
                "data",
            )

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("historical prices", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_company_info",
    annotations={
        "title": "Get Detailed Company Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(CompanyInfoOut)
def get_company_info(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Detailed company profile for one stock: long business summary, sector/industry, key executives, headquarters/website/employee count, and valuation & financial-highlight stats (market cap, P/E, margins, and similar).

    Use for "what does X do", company background, or a business overview. For the statement-level numbers (income/balance/cash flow) use get_financial_statements; for just the live price use get_stock_quote.

    Returns Markdown by default, or JSON when response_format='json'. An unknown ticker or upstream error returns a short error message.
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = make_ticker(ticker)
        info = ticker_obj.info
        _require_known(info, ticker)
        cur = info.get("currency") or "USD"

        def _md():
            result = f"# {safe_get(info, 'longName', ticker)} ({ticker})\n\n"

            result += "## Business Summary\n\n"
            summary = safe_get(info, "longBusinessSummary", "No description available")
            result += f"{summary}\n\n"

            result += "## Company Details\n\n"
            result += f"- **Sector:** {safe_get(info, 'sector')}\n"
            result += f"- **Industry:** {safe_get(info, 'industry')}\n"
            result += (
                f"- **Full Time Employees:** {safe_get(info, 'fullTimeEmployees'):,}\n"
                if safe_get(info, "fullTimeEmployees") != "N/A"
                else "- **Full Time Employees:** N/A\n"
            )
            result += f"- **Website:** {safe_get(info, 'website')}\n"
            result += f"- **Address:** {safe_get(info, 'address1')}, {safe_get(info, 'city')}, {safe_get(info, 'state')} {safe_get(info, 'zip')}\n"
            result += f"- **Country:** {safe_get(info, 'country')}\n"
            result += f"- **Phone:** {safe_get(info, 'phone')}\n\n"

            officers = safe_get(info, "companyOfficers", [])
            if officers and isinstance(officers, list):
                result += "## Key Executives\n\n"
                for officer in officers[:5]:
                    name = officer.get("name", "N/A")
                    title = officer.get("title", "N/A")
                    pay = officer.get("totalPay")
                    result += f"- **{name}** - {title}"
                    if pay:
                        result += f" (Compensation: {format_large_number(pay)})"
                    result += "\n"
                result += "\n"

            result += "## Key Statistics\n\n"
            result += f"- **Market Cap:** {format_large_number(safe_get(info, 'marketCap'))}\n"
            result += f"- **Enterprise Value:** {format_large_number(safe_get(info, 'enterpriseValue'))}\n"
            result += f"- **PE Ratio (Trailing):** {safe_get(info, 'trailingPE')}\n"
            result += f"- **PE Ratio (Forward):** {safe_get(info, 'forwardPE')}\n"
            result += f"- **PEG Ratio:** {safe_get(info, 'trailingPegRatio')}\n"
            result += f"- **Price to Book:** {safe_get(info, 'priceToBook')}\n"
            result += f"- **Price to Sales:** {safe_get(info, 'priceToSalesTrailing12Months')}\n"
            result += f"- **EPS (Trailing):** {format_currency(safe_get(info, 'trailingEps'), cur)}\n"
            result += f"- **EPS (Forward):** {format_currency(safe_get(info, 'forwardEps'), cur)}\n"
            result += f"- **Dividend Rate:** {format_currency(safe_get(info, 'dividendRate'), cur)}\n"
            result += f"- **Dividend Yield:** {format_dividend_yield(safe_get(info, 'dividendYield'))}\n"
            result += f"- **Ex-Dividend Date:** {safe_get(info, 'exDividendDate')}\n"
            result += f"- **Beta:** {safe_get(info, 'beta')}\n"
            result += f"- **52 Week High:** {format_currency(safe_get(info, 'fiftyTwoWeekHigh'), cur)}\n"
            result += f"- **52 Week Low:** {format_currency(safe_get(info, 'fiftyTwoWeekLow'), cur)}\n"
            result += f"- **50 Day Avg:** {format_currency(safe_get(info, 'fiftyDayAverage'), cur)}\n"
            result += f"- **200 Day Avg:** {format_currency(safe_get(info, 'twoHundredDayAverage'), cur)}\n"
            result += (
                f"- **Shares Outstanding:** {safe_get(info, 'sharesOutstanding'):,}\n"
                if safe_get(info, "sharesOutstanding") != "N/A"
                else "- **Shares Outstanding:** N/A\n"
            )
            result += (
                f"- **Float Shares:** {safe_get(info, 'floatShares'):,}\n"
                if safe_get(info, "floatShares") != "N/A"
                else "- **Float Shares:** N/A\n"
            )

            result += "\n## Financial Highlights\n\n"
            result += f"- **Revenue:** {format_large_number(safe_get(info, 'totalRevenue'))}\n"
            result += f"- **Revenue Per Share:** {format_currency(safe_get(info, 'revenuePerShare'), cur)}\n"
            result += f"- **Profit Margin:** {format_percentage(safe_get(info, 'profitMargins'))}\n"
            result += f"- **Operating Margin:** {format_percentage(safe_get(info, 'operatingMargins'))}\n"
            result += f"- **ROA (Return on Assets):** {format_percentage(safe_get(info, 'returnOnAssets'))}\n"
            result += f"- **ROE (Return on Equity):** {format_percentage(safe_get(info, 'returnOnEquity'))}\n"
            result += f"- **Total Cash:** {format_large_number(safe_get(info, 'totalCash'))}\n"
            result += f"- **Total Debt:** {format_large_number(safe_get(info, 'totalDebt'))}\n"
            result += f"- **Debt to Equity:** {safe_get(info, 'debtToEquity')}\n"
            result += f"- **Current Ratio:** {safe_get(info, 'currentRatio')}\n"
            result += f"- **Free Cash Flow:** {format_large_number(safe_get(info, 'freeCashflow'))}\n"

            return truncate_response(result, "")

        def _js():
            return truncate_json_response(
                _json(info),
                "Use markdown format for a summarized view.",
            )

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("company info", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_financial_statements",
    annotations={
        "title": "Get Company Financial Statements",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(StatementsOut)
def get_financial_statements(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Annual financial statements for one company: income statement, balance sheet, and cash flow statement, each with multiple years of data.

    Use for revenue, earnings, assets/liabilities, cash flow, or fundamental analysis. For headline ratios only use get_company_info; for forward projections use get_analyst_estimates. Quarterly data is not returned; request JSON for the complete machine-readable export.

    Returns Markdown by default, or JSON when response_format='json'. Companies without filed statements (for example some ETFs or ADRs) return empty sections or a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = make_ticker(ticker)

        income_stmt = ticker_obj.income_stmt
        balance_sheet = ticker_obj.balance_sheet
        cash_flow = ticker_obj.cashflow

        def _md():
            result = f"# Financial Statements: {ticker}\n\n"

            if income_stmt is not None and not income_stmt.empty:
                result += "## Income Statement (Annual)\n\n"
                result += dataframe_to_markdown(income_stmt, max_rows=30)
                result += "\n\n"

            if balance_sheet is not None and not balance_sheet.empty:
                result += "## Balance Sheet (Annual)\n\n"
                result += dataframe_to_markdown(balance_sheet, max_rows=30)
                result += "\n\n"

            if cash_flow is not None and not cash_flow.empty:
                result += "## Cash Flow Statement (Annual)\n\n"
                result += dataframe_to_markdown(cash_flow, max_rows=30)
                result += "\n\n"

            result += "*Note: Use JSON format for quarterly statements or complete data export.*"

            return truncate_response(
                result, "Request specific statement types separately if needed."
            )

        def _js():
            statements = {
                "incomeStatement": income_stmt,
                "balanceSheet": balance_sheet,
                "cashFlow": cash_flow,
            }
            result = {"ticker": ticker}
            result.update({k: _statement_to_dict(v) for k, v in statements.items()})
            result["lineItemCounts"] = {
                k: int(len(v))
                for k, v in statements.items()
                if v is not None and not v.empty
            }
            return truncate_json_response(
                _json(result),
                "Use markdown format for a summarized view.",
            )

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("financial statements", ticker, e)


@mcp.tool(
    structured_output=False,
    name="compare_stocks",
    annotations={
        "title": "Compare Multiple Stocks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(CompareOut)
def compare_stocks(
    tickers: Annotated[
        List[str],
        Field(
            description="List of 2-10 stock ticker symbols to compare (e.g., ['AAPL', 'MSFT', 'GOOGL'])",
            min_length=2,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Side-by-side comparison of 2-10 stocks across key metrics (price, market cap, P/E, EPS, dividend yield, 52-week range, and period performance) with brief auto-generated insights.

    Use for "which is better, X or Y", peer/relative comparison, or screening a small set. For a deep dive on a single name use get_stock_quote or get_company_info.

    Pass 2-10 tickers in the tickers list. Returns a Markdown comparison table by default, or JSON when response_format='json'. A ticker that fails to resolve is reported per-symbol rather than failing the whole call.
    """
    tickers = [_norm_ticker(t) for t in tickers]
    try:
        comparison_data = []

        for ticker in tickers:
            try:
                ticker_obj = make_ticker(ticker)
                info = ticker_obj.info
                _require_known(info, ticker)

                data = {
                    "Ticker": ticker,
                    "Name": safe_get(info, "longName", ticker),
                    "Currency": info.get("currency"),
                    "Price": safe_get(info, "currentPrice"),
                    "Change%": safe_get(info, "regularMarketChangePercent"),
                    "MarketCap": safe_get(info, "marketCap"),
                    "PE": safe_get(info, "trailingPE"),
                    "EPS": safe_get(info, "trailingEps"),
                    "DivYield%": safe_get(info, "dividendYield"),
                    "Beta": safe_get(info, "beta"),
                    "52WkHigh": safe_get(info, "fiftyTwoWeekHigh"),
                    "52WkLow": safe_get(info, "fiftyTwoWeekLow"),
                    "Volume": safe_get(info, "volume"),
                    "AvgVolume": safe_get(info, "averageVolume"),
                    "Sector": safe_get(info, "sector"),
                    "Industry": safe_get(info, "industry"),
                }
                comparison_data.append(data)
            except Exception as e:
                comparison_data.append({"Ticker": ticker, "Error": str(e)})

        if all("Error" in d for d in comparison_data):
            raise ToolError(
                "None of the tickers could be fetched: "
                + "; ".join(f"{d['Ticker']}: {d['Error']}" for d in comparison_data)
            )

        def _md():
            result = f"# Stock Comparison: {', '.join(tickers)}\n\n"

            df = pd.DataFrame(comparison_data)
            result += dataframe_to_markdown(df)

            result += "\n\n## Key Insights\n\n"

            valid_data = [d for d in comparison_data if "Error" not in d]
            if valid_data:

                def _numeric(items):
                    return [(t, v) for t, v in items if isinstance(v, (int, float))]

                prices = _numeric((d["Ticker"], d["Price"]) for d in valid_data)
                # Prices in different currencies do not compare.
                if prices and len({d.get("Currency") for d in valid_data}) == 1:
                    highest = max(prices, key=lambda x: x[1])
                    result += f"- **Highest Price:** {highest[0]} at {format_currency(highest[1])}\n"

                market_caps = _numeric(
                    (d["Ticker"], d["MarketCap"]) for d in valid_data
                )
                if market_caps:
                    largest = max(market_caps, key=lambda x: x[1])
                    result += f"- **Largest Market Cap:** {largest[0]} at {format_large_number(largest[1])}\n"

                div_yields = _numeric((d["Ticker"], d["DivYield%"]) for d in valid_data)
                if div_yields:
                    best_div = max(div_yields, key=lambda x: x[1])
                    result += f"- **Highest Dividend Yield:** {best_div[0]} at {format_dividend_yield(best_div[1])}\n"

            return truncate_response(result, "")

        def _js():
            result = {"tickers": tickers, "comparison": comparison_data}
            return truncate_json_response(_json(result), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("comparison", ", ".join(tickers), e)


@mcp.tool(
    structured_output=False,
    name="get_analyst_recommendations",
    annotations={
        "title": "Get Analyst Recommendations and Price Targets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(RecommendationsOut)
def get_analyst_recommendations(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Wall Street analyst view on one stock: price targets (high/mean/low), consensus rating, the buy/hold/sell recommendation-trend breakdown, and recent upgrades/downgrades.

    Use for "what do analysts think of X", ratings, or sentiment. For forward EPS/revenue/growth projections use get_analyst_estimates instead: this tool is ratings and targets, that one is the numeric estimates. Not for news-driven sentiment (use get_market_news). Small caps often have few or no covering analysts, so a thin consensus carries little weight.

    Returns Markdown by default, or JSON when response_format='json'. A stock with no analyst coverage returns the available fields as N/A; errors return a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = make_ticker(ticker)
        info = ticker_obj.info
        _require_known(info, ticker)
        cur = info.get("currency") or "USD"

        # Recommendation trend: modern yfinance returns columns
        # [period, strongBuy, buy, hold, sell, strongSell] with a RangeIndex.
        try:
            recommendations = ticker_obj.recommendations
        except Exception:
            recommendations = None

        # Upgrades/downgrades history is a separate (dated) frame.
        try:
            upgrades = ticker_obj.upgrades_downgrades
        except Exception:
            upgrades = None

        def _md():
            result = f"# Analyst Recommendations: {ticker}\n\n"

            result += "## Price Targets\n\n"
            result += f"- **Target High:** {format_currency(safe_get(info, 'targetHighPrice'), cur)}\n"
            result += f"- **Target Mean:** {format_currency(safe_get(info, 'targetMeanPrice'), cur)}\n"
            result += f"- **Target Low:** {format_currency(safe_get(info, 'targetLowPrice'), cur)}\n"
            result += f"- **Target Median:** {format_currency(safe_get(info, 'targetMedianPrice'), cur)}\n"
            result += f"- **Current Price:** {format_currency(safe_get(info, 'currentPrice'), cur)}\n\n"

            current = safe_get(info, "currentPrice")
            target = safe_get(info, "targetMeanPrice")
            if (
                isinstance(current, (int, float))
                and isinstance(target, (int, float))
                and current
            ):
                upside = ((target - current) / current) * 100
                result += f"**Potential from Mean Target:** {upside:+.2f}%\n\n"

            result += "## Analyst Consensus\n\n"
            result += f"- **Number of Analysts:** {safe_get(info, 'numberOfAnalystOpinions')}\n"
            rec_mean = safe_get(info, "recommendationMean")
            result += f"- **Recommendation Mean:** {rec_mean} "
            if isinstance(rec_mean, (int, float)):
                if rec_mean <= 2.0:
                    result += "(Strong Buy/Buy)\n"
                elif rec_mean <= 3.0:
                    result += "(Hold)\n"
                else:
                    result += "(Sell/Underperform)\n"
            else:
                result += "\n"
            result += (
                f"- **Recommendation Key:** {safe_get(info, 'recommendationKey')}\n\n"
            )

            if recommendations is not None and not recommendations.empty:
                result += "## Recommendation Trend\n\n"
                result += "*Number of analysts by rating, by period (0m = current month, -1m = last month, ...).*\n\n"
                result += dataframe_to_markdown(recommendations)
                result += "\n\n"

            if upgrades is not None and not upgrades.empty:
                result += "## Recent Upgrades / Downgrades (Last 10)\n\n"
                recent = upgrades.head(10).copy()
                try:
                    recent.index = recent.index.strftime("%Y-%m-%d")
                except (AttributeError, ValueError):
                    pass
                result += dataframe_to_markdown(recent)
                result += "\n"

            if (recommendations is None or recommendations.empty) and (
                upgrades is None or upgrades.empty
            ):
                result += "No recommendation trend data available.\n"

            return truncate_response(result, "")

        def _js():
            result = {
                "ticker": ticker,
                "priceTargets": {
                    "high": safe_get(info, "targetHighPrice"),
                    "mean": safe_get(info, "targetMeanPrice"),
                    "low": safe_get(info, "targetLowPrice"),
                    "median": safe_get(info, "targetMedianPrice"),
                    "currentPrice": safe_get(info, "currentPrice"),
                },
                "consensus": {
                    "numberOfAnalysts": safe_get(info, "numberOfAnalystOpinions"),
                    "recommendationMean": safe_get(info, "recommendationMean"),
                    "recommendationKey": safe_get(info, "recommendationKey"),
                },
                "recommendationTrend": recommendations.to_dict(orient="records")
                if recommendations is not None and not recommendations.empty
                else [],
                # Same last-10 cap the markdown branch applies. Without it this
                # frame is the full rating history, and on a widely covered
                # stock that is ~260,000 characters - over the response limit,
                # so the whole tool answered `response_too_large` and returned
                # no targets and no consensus either. Measured on NVDA, AAPL,
                # MSFT, PLTR and F: every one of them, markdown fine, JSON dead.
                "upgradesDowngrades": upgrades.head(10)
                .reset_index()
                .to_dict(orient="records")
                if upgrades is not None and not upgrades.empty
                else [],
            }
            return truncate_json_response(_json(result), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("analyst recommendations", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_market_news",
    annotations={
        "title": "Get Latest Financial News",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(NewsOut)
def get_market_news(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol to get news for (e.g., 'AAPL', 'TSLA', 'NVDA')",
            min_length=1,
            max_length=10,
        ),
    ],
    count: Annotated[
        int,
        Field(description="Number of news articles to return (1-20)", ge=1, le=20),
    ] = 10,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Latest news articles for one stock; each item has a title, publisher/source, publish date, a short summary, and a link.

    Use for "what's the latest news on X", recent headlines, or catalysts. Returns news only: for price use get_stock_quote, for fundamentals use the financials tools.

    count sets how many articles to return (1-20, default 10). Returns Markdown by default, or JSON when response_format='json'. No recent news returns a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        # Yahoo's feed for a ticker mixes in market wraps and other companies'
        # stories that merely mention it. Fetch extra, put the ones led by this
        # ticker (first tag, or the symbol in the headline) ahead, and keep each
        # article's tags so the caller can judge the rest.
        articles = make_ticker(ticker).get_news(count=min(count * 2, 40)) or []

        def tags(article: Dict[str, Any]) -> List[str]:
            fin = (article.get("content", article) or {}).get("finance") or {}
            return [
                x.get("symbol")
                for x in fin.get("stockTickers") or []
                if x.get("symbol")
            ]

        def about(article: Dict[str, Any]) -> bool:
            t = tags(article)
            title = (article.get("content", article) or {}).get("title") or ""
            return (bool(t) and t[0] == ticker) or re.search(
                rf"\b{re.escape(ticker)}\b", title
            ) is not None

        articles = sorted(articles, key=lambda a: not about(a))[:count]

        # Modern yfinance nests each article's fields under a "content" key.
        def field(article: Dict[str, Any]) -> Dict[str, Any]:
            return article.get("content", article) or {}

        def link(c: Dict[str, Any]) -> str:
            for key in ("canonicalUrl", "clickThroughUrl"):
                val = c.get(key)
                if isinstance(val, dict) and val.get("url"):
                    return val["url"]
            return "N/A"

        def provider(c: Dict[str, Any]) -> str:
            p = c.get("provider")
            if isinstance(p, dict):
                return p.get("displayName", "N/A")
            return "N/A"

        if not articles:
            return f"No recent news found for {ticker}."

        def _md():
            result = f"# Latest News: {ticker}\n\n"
            for i, article in enumerate(articles[:count], 1):
                c = field(article)
                title = c.get("title", "Untitled")
                date = c.get("pubDate", c.get("displayTime", ""))
                summary = c.get("summary") or c.get("description") or ""
                if len(summary) > 400:
                    summary = summary[:400].rstrip() + "..."
                result += f"## {i}. {title}\n"
                tagged = ", ".join(tags(article)[:6])
                meta = " | ".join(
                    x
                    for x in [provider(c), date, f"tickers: {tagged}" if tagged else ""]
                    if x and x != "N/A"
                )
                if meta:
                    result += f"*{meta}*\n\n"
                if summary:
                    result += f"{summary}\n\n"
                result += f"[Read more]({link(c)})\n\n"
            return truncate_response(
                result, "Request fewer articles for a shorter response."
            )

        def _js():
            items = []
            for article in articles[:count]:
                c = field(article)
                items.append(
                    {
                        "title": c.get("title"),
                        "provider": provider(c),
                        "pubDate": c.get("pubDate", c.get("displayTime")),
                        "summary": c.get("summary") or c.get("description"),
                        "url": link(c),
                        "tickers": tags(article),
                        "primarilyAbout": about(article),
                    }
                )
            payload = {"ticker": ticker, "count": len(items), "news": items}
            return truncate_json_response(_json(payload), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("market news", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_options_chain",
    annotations={
        "title": "Get Options Chain",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(OptionsOut)
def get_options_chain(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'SPY', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    expiration_date: Annotated[
        str,
        Field(
            description="Options expiration date as 'YYYY-MM-DD'. Leave empty to list all available expiration dates instead.",
        ),
    ] = "",
    option_type: Annotated[
        OptionType,
        Field(
            description="Which side of the chain to return: 'calls', 'puts', or 'both'"
        ),
    ] = OptionType.BOTH,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Equity options data for one underlying, in two modes: call with no expiration_date to LIST every available expiration date; call again with a specific 'YYYY-MM-DD' to get that expiration's chain (strike, bid/ask, last, volume, open interest, implied volatility).

    Use for options pricing, implied volatility, or open-interest analysis. option_type selects 'calls', 'puts', or 'both'. Always discover the valid dates first (call with no date) before requesting a chain, since only listed expirations work.

    Returns Markdown by default, or JSON when response_format='json'. A ticker with no listed options returns a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        t = make_ticker(ticker)
        expirations = list(t.options or [])

        if not expirations:
            return f"No options data available for {ticker}. It may not have listed options."

        # No date requested -> return the menu of available expirations.
        if not expiration_date.strip():

            def _md_dates():
                result = f"# Options Expirations: {ticker}\n\n"
                result += f"**{len(expirations)} available expiration dates:**\n\n"
                result += ", ".join(expirations)
                result += "\n\n*Call again with an `expiration_date` to get the chain.*"
                return result

            return _respond(
                response_format,
                _md_dates,
                lambda: _json({"ticker": ticker, "expirationDates": expirations}),
            )

        if expiration_date not in expirations:
            raise ToolError(
                f"'{expiration_date}' is not an available expiration for {ticker}. "
                f"Available dates: {', '.join(expirations)}"
            )

        chain = t.option_chain(expiration_date)
        want_calls = option_type in (OptionType.CALLS, OptionType.BOTH)
        want_puts = option_type in (OptionType.PUTS, OptionType.BOTH)
        spot = (getattr(chain, "underlying", None) or {}).get("regularMarketPrice")

        def near_money(df: pd.DataFrame, n: int) -> pd.DataFrame:
            """The n strikes closest to the current price, in strike order.

            A chain runs to 70+ strikes a side and starts deep in the money,
            so the first rows are the least useful ones and a whole chain is
            over the response limit. Without a spot price, keep the first n.
            """
            if df is None or df.empty or n >= len(df):
                return df
            if not isinstance(spot, (int, float)):
                return df.head(n)
            return df.loc[(df["strike"] - spot).abs().nsmallest(n).index].sort_values(
                "strike"
            )

        def _md():
            result = f"# Options Chain: {ticker} ({expiration_date})\n\n"
            if isinstance(spot, (int, float)):
                result += f"Underlying: {spot:,.2f}. Showing the 40 strikes nearest it per side.\n\n"
            if want_calls:
                result += "## Calls\n\n"
                result += dataframe_to_markdown(
                    near_money(chain.calls, 40), max_rows=40
                )
                result += "\n\n"
            if want_puts:
                result += "## Puts\n\n"
                result += dataframe_to_markdown(near_money(chain.puts, 40), max_rows=40)
                result += "\n\n"
            return truncate_response(
                result, "Request a single option_type for more strikes."
            )

        def _js():
            sides = [
                x for x, want in (("calls", want_calls), ("puts", want_puts)) if want
            ]
            total = max(len(getattr(chain, x)) for x in sides)
            keep = total
            while True:
                payload: Dict[str, Any] = {
                    "ticker": ticker,
                    "expirationDate": expiration_date,
                    "underlyingPrice": spot,
                }
                for x in sides:
                    payload[x] = near_money(getattr(chain, x), keep).to_dict(
                        orient="records"
                    )
                payload["strikesPerSide"] = keep
                payload["truncated"] = keep < total
                if payload["truncated"]:
                    payload["note"] = (
                        f"The {keep} strikes nearest the underlying price per side, of {total}. "
                        "Request a single option_type for more."
                    )
                text = _json(payload)
                if len(text) <= CHARACTER_LIMIT or keep <= 1:
                    return truncate_json_response(text, "")
                keep = keep * 3 // 4

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("options chain", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_holders",
    annotations={
        "title": "Get Stock Ownership and Insider Activity",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(HoldersOut)
def get_holders(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    holder_type: Annotated[
        HolderType,
        Field(
            description="Type of ownership data: 'institutional', 'mutualfund', 'major', 'insider_transactions' (each trade), 'insider_purchases' (6-month net buying summary), or 'insider_roster' (insiders and their current stakes)"
        ),
    ] = HolderType.INSTITUTIONAL,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Ownership and insider activity for one stock, selected by holder_type: 'institutional' (top institutional holders), 'mutualfund' (top fund holders), 'major' (insider-vs-institutional ownership % breakdown), 'insider_transactions' (recent insider buys and sells, one row per trade), 'insider_purchases' (net insider buying vs selling over the last 6 months), or 'insider_roster' (each insider, their position and shares held).

    Use for "who owns X", institutional ownership, or insider trading activity. One holder_type per call: call again to get a different view. Not for share count, float or valuation (use get_company_info) or for analyst opinion (use get_analyst_recommendations). Institutional and fund holdings come from quarterly filings, so they can be a few months old; insider trades are filed within days and are the fresher signal.

    Returns Markdown by default, or JSON when response_format='json'. Missing data for the chosen category returns a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        t = make_ticker(ticker)
        labels = {
            HolderType.INSTITUTIONAL: (
                "Institutional Holders",
                lambda: t.institutional_holders,
            ),
            HolderType.MUTUALFUND: (
                "Mutual Fund Holders",
                lambda: t.mutualfund_holders,
            ),
            HolderType.MAJOR: ("Major Holders Breakdown", lambda: t.major_holders),
            HolderType.INSIDER_TRANSACTIONS: (
                "Insider Transactions",
                lambda: t.insider_transactions,
            ),
            HolderType.INSIDER_PURCHASES: (
                "Insider Net Buying (Last 6 Months)",
                lambda: t.insider_purchases,
            ),
            HolderType.INSIDER_ROSTER: (
                "Insider Roster",
                lambda: t.insider_roster_holders,
            ),
        }
        title, getter = labels[holder_type]
        df = getter()

        if df is None or (hasattr(df, "empty") and df.empty):
            return f"No {title.lower()} data available for {ticker}."

        def _md():
            result = f"# {title}: {ticker}\n\n"
            result += dataframe_to_markdown(df, max_rows=40)
            return truncate_response(
                result, "Use JSON format for the complete dataset."
            )

        def _js():
            records = df.reset_index().to_dict(orient="records")
            # Insider transactions run to hundreds of rows; keep the newest
            # that fit rather than refusing the whole payload.
            insider = holder_type == HolderType.INSIDER_TRANSACTIONS
            return _fit_records(
                records[::-1] if insider else records,  # Yahoo lists trades newest first
                {"ticker": ticker, "holderType": holder_type.value},
                "data",
                hint="Older trades did not fit the response limit.",
                newest_first=insider,
            )

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("holders", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_dividends_splits",
    annotations={
        "title": "Get Dividend and Stock Split History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(DividendsOut)
def get_dividends_splits(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'KO', 'JNJ')",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Full dividend payment history (with a trailing-period summary) and the stock-split history for one stock.

    Use for dividend-income analysis, payment dates and amounts, dividend growth, or past split events. For the current/forward dividend yield use get_stock_quote; for price history use get_historical_prices.

    Returns Markdown by default, or JSON when response_format='json'. A stock that pays no dividend or has never split returns a short message noting that none exist.
    """
    ticker = _norm_ticker(ticker)
    try:
        t = make_ticker(ticker)
        dividends = t.dividends
        splits = t.splits

        has_div = dividends is not None and len(dividends) > 0
        has_splits = splits is not None and len(splits) > 0

        if not has_div and not has_splits:
            return f"No dividend or split history available for {ticker} (it may not pay dividends)."

        def _md():
            result = f"# Dividends & Splits: {ticker}\n\n"

            if has_div:
                latest = dividends.tail(12)
                result += "## Dividend History\n\n"
                result += f"- **Total payments on record:** {len(dividends)}\n"
                result += (
                    f"- **First payment:** {dividends.index[0].strftime('%Y-%m-%d')}\n"
                )
                result += f"- **Most recent:** {format_currency(float(dividends.iloc[-1]))} on {dividends.index[-1].strftime('%Y-%m-%d')}\n"
                ttm = float(dividends.tail(4).sum())
                result += f"- **Trailing ~12mo (last 4 payments):** {format_currency(ttm)}\n\n"
                result += "### Recent payments (last 12)\n\n"
                div_df = latest.rename("Dividend").to_frame()
                div_df.index = div_df.index.strftime("%Y-%m-%d")
                result += dataframe_to_markdown(div_df, max_rows=12)
                result += "\n\n"
            else:
                result += "## Dividend History\n\nNo dividends on record.\n\n"

            if has_splits:
                result += "## Stock Split History\n\n"
                split_df = splits.rename("Split Ratio").to_frame()
                split_df.index = split_df.index.strftime("%Y-%m-%d")
                result += dataframe_to_markdown(split_df, max_rows=40)
            else:
                result += "## Stock Split History\n\nNo splits on record.\n"

            return truncate_response(
                result, "Use JSON format for the complete history."
            )

        def _js():
            payload = {
                "ticker": ticker,
                "dividends": [
                    {"date": d.strftime("%Y-%m-%d"), "amount": float(v)}
                    for d, v in dividends.items()
                ]
                if has_div
                else [],
                "splits": [
                    {"date": d.strftime("%Y-%m-%d"), "ratio": float(v)}
                    for d, v in splits.items()
                ]
                if has_splits
                else [],
            }
            return truncate_json_response(_json(payload), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("dividends and splits", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_analyst_estimates",
    annotations={
        "title": "Get Forward Analyst Estimates",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(EstimatesOut)
def get_analyst_estimates(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Forward-looking analyst estimates for one stock: price targets, EPS and revenue estimates by period (current and next quarter and year), and growth estimates.

    Use for projected/expected numbers and forecasts. This complements get_analyst_recommendations: that tool returns ratings and the recommendation trend, this one returns the numeric forward estimates.

    Returns Markdown by default, or JSON when response_format='json'. A stock without analyst coverage returns the available fields as N/A or a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        t = make_ticker(ticker)
        targets = t.analyst_price_targets or {}
        eps_est = t.earnings_estimate
        rev_est = t.revenue_estimate
        growth = t.growth_estimates

        def has(df) -> bool:
            return df is not None and hasattr(df, "empty") and not df.empty

        if not targets and not has(eps_est) and not has(rev_est):
            return f"No analyst estimate data available for {ticker}."

        def _md():
            result = f"# Analyst Estimates: {ticker}\n\n"

            if targets:
                result += "## Price Target\n\n"
                result += f"- **Current:** {format_currency(targets.get('current'))}\n"
                result += f"- **Mean:** {format_currency(targets.get('mean'))}\n"
                result += f"- **Median:** {format_currency(targets.get('median'))}\n"
                result += f"- **High:** {format_currency(targets.get('high'))}\n"
                result += f"- **Low:** {format_currency(targets.get('low'))}\n"
                cur, mean = targets.get("current"), targets.get("mean")
                if (
                    isinstance(cur, (int, float))
                    and isinstance(mean, (int, float))
                    and cur
                ):
                    result += f"- **Upside to mean target:** {((mean - cur) / cur) * 100:+.2f}%\n"
                result += "\n"

            if has(eps_est):
                result += "## EPS Estimate\n\n"
                result += "*Periods: 0q = current quarter, +1q = next, 0y = current year, +1y = next.*\n\n"
                result += dataframe_to_markdown(eps_est)
                result += "\n\n"

            if has(rev_est):
                result += "## Revenue Estimate\n\n"
                result += dataframe_to_markdown(rev_est)
                result += "\n\n"

            if has(growth):
                result += "## Growth Estimates\n\n"
                result += dataframe_to_markdown(growth)
                result += "\n"

            return truncate_response(
                result, "Use JSON format for the complete dataset."
            )

        def _js():

            def df_records(df):
                return df.reset_index().to_dict(orient="records") if has(df) else []

            payload = {
                "ticker": ticker,
                "priceTargets": targets,
                "earningsEstimate": df_records(eps_est),
                "revenueEstimate": df_records(rev_est),
                "growthEstimates": df_records(growth),
            }
            return truncate_json_response(_json(payload), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("analyst estimates", ticker, e)


@mcp.tool(
    structured_output=False,
    name="search_symbols",
    annotations={
        "title": "Search for Ticker Symbols",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(SearchOut)
def search_symbols(
    query: Annotated[
        str,
        Field(
            description="Company name or keyword to search for (e.g., 'Apple', 'electric vehicles', 'Berkshire')",
            min_length=1,
            max_length=100,
        ),
    ],
    count: Annotated[
        int,
        Field(description="Maximum number of matches to return (1-20)", ge=1, le=20),
    ] = 8,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Resolve a company name or keyword to ticker symbols; each match returns the symbol, name, exchange, and instrument type (equity, ETF, and so on).

    Use this first when you have a company or brand name but not its ticker, then pass the resolved symbol to the other tools. Skip it when you already have a valid ticker. Not for fetching prices or fundamentals. A name often matches several listings (the US share, foreign listings, ETFs): choose by exchange and type, not just the first row.

    query is the name/keyword to search; count caps the number of matches (1-20, default 8). Returns Markdown by default, or JSON when response_format='json'. No matches returns a short message.
    """
    query = query.strip()
    try:
        session = _get_session()
        kwargs = {"max_results": count, "news_count": 0}
        if session is not None:
            kwargs["session"] = session
        try:
            search = yf.Search(query, **kwargs)
        except Exception:
            search = yf.Search(query)  # fall back to defaults if kwargs unsupported

        quotes = (search.quotes or [])[:count]
        if not quotes:
            return f"No symbols found matching '{query}'."

        def _md():
            result = f'# Symbol Search: "{query}"\n\n'
            for q in quotes:
                sym = q.get("symbol", "?")
                name = q.get("longname") or q.get("shortname") or ""
                exch = q.get("exchDisp", "")
                typ = q.get("typeDisp", q.get("quoteType", ""))
                extra = ", ".join(x for x in [exch, typ, q.get("sector", "")] if x)
                result += f"- **{sym}** — {name}"
                if extra:
                    result += f" ({extra})"
                result += "\n"
            return truncate_response(result, "")

        def _js():
            items = [
                {
                    "symbol": q.get("symbol"),
                    "name": q.get("longname") or q.get("shortname"),
                    "exchange": q.get("exchDisp"),
                    "type": q.get("typeDisp", q.get("quoteType")),
                    "sector": q.get("sector"),
                    "industry": q.get("industry"),
                }
                for q in quotes
            ]
            payload = {"query": query, "count": len(items), "results": items}
            return truncate_json_response(_json(payload), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("symbol search", query, e)


@mcp.tool(
    structured_output=False,
    name="get_market_status",
    annotations={
        "title": "Get Market Status and Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(MarketStatusOut)
def get_market_status(
    region: Annotated[
        MarketRegion,
        Field(
            description="Market: US, GB, ASIA, EUROPE, RATES, COMMODITIES, CURRENCIES or CRYPTOCURRENCIES"
        ),
    ] = MarketRegion.US,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Whether a stock market is currently open or closed for a given region, with trading-session timing and a summary of that region's major indices.

    Use for "is the US market open", market hours, or a quick index overview. region is one of US (default), GB, ASIA or EUROPE for equity markets, or RATES, COMMODITIES, CURRENCIES or CRYPTOCURRENCIES for those asset classes; other country codes are not accepted. This is market-wide, not per-stock: use get_stock_quote for an individual price, and get_sector_overview for sector performance.

    Returns Markdown by default, or JSON when response_format='json'. An unrecognized region returns a short message.
    """
    region = region.value
    try:
        session = _get_session()
        try:
            mkt = (
                yf.Market(region, session=session)
                if session is not None
                else yf.Market(region)
            )
        except Exception:
            mkt = yf.Market(region)

        status = mkt.status or {}
        summary = mkt.summary or {}

        if not status and not summary:
            return f"No market data available for region '{region}'. Try a code like 'US', 'GB', or 'JP'."

        def _md():
            result = f"# Market Status: {status.get('name', region)}\n\n"
            state = status.get("status", "unknown")
            result += f"- **Status:** {str(state).upper()}\n"
            if status.get("message"):
                result += f"- {status['message']}\n"
            if status.get("open"):
                result += f"- **Open:** {status['open']}\n"
            if status.get("close"):
                result += f"- **Close:** {status['close']}\n"
            tz = status.get("tz")
            if tz:
                result += f"- **Timezone:** {tz}\n"

            if summary:
                result += "\n## Major Indices\n\n"
                for _key, idx in summary.items():
                    if not isinstance(idx, dict):
                        continue
                    name = idx.get("shortName", idx.get("symbol", "?"))
                    price = idx.get("regularMarketPrice")
                    chg = idx.get("regularMarketChangePercent")
                    price_val = price.get("raw") if isinstance(price, dict) else price
                    chg_val = chg.get("raw") if isinstance(chg, dict) else chg
                    line = f"- **{name}:** "
                    line += (
                        format_currency(price_val)
                        if isinstance(price_val, (int, float))
                        else "N/A"
                    )
                    if isinstance(chg_val, (int, float)):
                        line += f" ({chg_val:+.2f}%)"
                    result += line + "\n"

            return truncate_response(result, "")

        def _js():
            payload = {"region": region, "status": status, "summary": summary}
            return truncate_json_response(_json(payload), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("market status", region, e)


class Screener(str, Enum):
    """Yahoo's predefined screeners (the lists behind finance.yahoo.com/screener)."""

    DAY_GAINERS = "day_gainers"
    DAY_LOSERS = "day_losers"
    MOST_ACTIVES = "most_actives"
    MOST_SHORTED_STOCKS = "most_shorted_stocks"
    SMALL_CAP_GAINERS = "small_cap_gainers"
    AGGRESSIVE_SMALL_CAPS = "aggressive_small_caps"
    GROWTH_TECHNOLOGY_STOCKS = "growth_technology_stocks"
    UNDERVALUED_GROWTH_STOCKS = "undervalued_growth_stocks"
    UNDERVALUED_LARGE_CAPS = "undervalued_large_caps"
    TOP_ETFS_US = "top_etfs_us"
    TOP_PERFORMING_ETFS = "top_performing_etfs"
    TECHNOLOGY_ETFS = "technology_etfs"
    BOND_ETFS = "bond_etfs"
    TOP_MUTUAL_FUNDS = "top_mutual_funds"
    SOLID_LARGE_GROWTH_FUNDS = "solid_large_growth_funds"
    SOLID_MIDCAP_GROWTH_FUNDS = "solid_midcap_growth_funds"
    CONSERVATIVE_FOREIGN_FUNDS = "conservative_foreign_funds"
    HIGH_YIELD_BOND = "high_yield_bond"
    PORTFOLIO_ANCHORS = "portfolio_anchors"


class SectorKey(str, Enum):
    """Yahoo Finance sector keys."""

    BASIC_MATERIALS = "basic-materials"
    COMMUNICATION_SERVICES = "communication-services"
    CONSUMER_CYCLICAL = "consumer-cyclical"
    CONSUMER_DEFENSIVE = "consumer-defensive"
    ENERGY = "energy"
    FINANCIAL_SERVICES = "financial-services"
    HEALTHCARE = "healthcare"
    INDUSTRIALS = "industrials"
    REAL_ESTATE = "real-estate"
    TECHNOLOGY = "technology"
    UTILITIES = "utilities"


def _num(value: Any, spec: str = ".2f", suffix: str = "") -> str:
    """Format a finite number, or '-' for anything missing or non-finite."""
    if isinstance(value, (int, float)) and math.isfinite(value):
        return format(value, spec) + suffix
    return "-"


def _records(df: Any, limit: int) -> List[Dict[str, Any]]:
    """A frame as a list of plain records with its index as a column, capped."""
    if df is None or getattr(df, "empty", True):
        return []
    out = df.head(limit).reset_index()
    out.columns = [str(c) for c in out.columns]
    return out.to_dict(orient="records")


def _date(value: Any) -> Any:
    """ISO date string for a date/datetime/Timestamp, else the value unchanged."""
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else value


@mcp.tool(
    structured_output=False,
    name="get_earnings",
    annotations={
        "title": "Get Earnings Dates and Surprises",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(EarningsOut)
def get_earnings(
    ticker: Annotated[
        str,
        Field(
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')",
            min_length=1,
            max_length=10,
        ),
    ],
    limit: Annotated[
        int,
        Field(
            description="How many earnings dates to return, upcoming and past (1-40)",
            ge=1,
            le=40,
        ),
    ] = 12,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Next earnings date for one stock (with days until it, consensus EPS and revenue range) plus its earnings history: each past report's EPS estimate, reported EPS and surprise %. Also returns the next ex-dividend date.

    Use before opening or holding a position through earnings, to check the earnings track record (beats vs misses), or for "when does X report". For forward EPS/revenue estimates by period use get_analyst_estimates; for every company reporting in a date range use get_earnings_calendar; for full income statements use get_financial_statements. limit counts upcoming and past dates together, newest first.

    Returns Markdown by default, or JSON when response_format='json'. A symbol with no earnings (an ETF, an index) returns a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        t = make_ticker(ticker)
        try:
            cal = t.calendar or {}
        except Exception:
            cal = {}
        try:
            dates = t.get_earnings_dates(limit=limit)
            if dates is not None:
                dates = dates.head(limit)  # yfinance returns at least 25 rows whatever the limit
        except Exception:
            dates = None

        if not cal.get("Earnings Date") and (dates is None or dates.empty):
            return f"No earnings data available for {ticker} (ETFs and indices do not report earnings)."

        today = pd.Timestamp.now().date()
        next_dates = cal.get("Earnings Date") or []
        next_date = next_dates[0] if next_dates else None
        days_until = (next_date - today).days if next_date else None

        history = []
        if dates is not None and not dates.empty:
            for idx, row in dates.iterrows():
                history.append(
                    {
                        "date": idx.strftime("%Y-%m-%d"),
                        "epsEstimate": row.get("EPS Estimate"),
                        "reportedEps": row.get("Reported EPS"),
                        "surprisePercent": row.get("Surprise(%)"),
                    }
                )
        reported = [h for h in history if _num(h["surprisePercent"]) != "-"]
        beats = sum(1 for h in reported if h["surprisePercent"] > 0)

        def _md():
            result = f"# Earnings: {ticker}\n\n"
            if next_date:
                result += f"- **Next earnings:** {_date(next_date)}"
                if len(next_dates) > 1:
                    result += f" to {_date(next_dates[-1])} (window)"
                result += f" ({days_until} days away)\n"
            if cal.get("Earnings Average") is not None:
                result += (
                    f"- **EPS estimate:** {format_currency(cal.get('Earnings Average'))} "
                    f"(range {format_currency(cal.get('Earnings Low'))} to {format_currency(cal.get('Earnings High'))})\n"
                )
            if cal.get("Revenue Average") is not None:
                result += (
                    f"- **Revenue estimate:** {format_large_number(cal.get('Revenue Average'))} "
                    f"(range {format_large_number(cal.get('Revenue Low'))} to {format_large_number(cal.get('Revenue High'))})\n"
                )
            if cal.get("Ex-Dividend Date"):
                result += f"- **Ex-dividend date:** {_date(cal['Ex-Dividend Date'])}\n"
            if reported:
                result += f"- **Track record:** beat the EPS estimate in {beats} of the last {len(reported)} reports\n"
            if history:
                result += "\n## Earnings History\n\n"
                result += "| Date | EPS Estimate | Reported EPS | Surprise |\n|---|---|---|---|\n"
                for h in history:
                    result += (
                        f"| {h['date']} | {_num(h['epsEstimate'])} | {_num(h['reportedEps'])} | "
                        f"{_num(h['surprisePercent'], '+.2f', '%')} |\n"
                    )
            return truncate_response(result, "")

        def _js():
            payload = {
                "ticker": ticker,
                "nextEarningsDate": _date(next_date) if next_date else None,
                "nextEarningsWindow": [_date(d) for d in next_dates],
                "daysUntilEarnings": days_until,
                "epsEstimate": {
                    "average": cal.get("Earnings Average"),
                    "low": cal.get("Earnings Low"),
                    "high": cal.get("Earnings High"),
                },
                "revenueEstimate": {
                    "average": cal.get("Revenue Average"),
                    "low": cal.get("Revenue Low"),
                    "high": cal.get("Revenue High"),
                },
                "exDividendDate": _date(cal.get("Ex-Dividend Date")),
                "beats": beats,
                "reportsWithSurprise": len(reported),
                "history": history,
            }
            return truncate_json_response(_json(payload), "Lower the limit.")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("earnings", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_earnings_calendar",
    annotations={
        "title": "Get Market-Wide Earnings Calendar",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(EarningsCalendarOut)
def get_earnings_calendar(
    start_date: Annotated[
        str | None,
        Field(description="First day, YYYY-MM-DD. Defaults to today."),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="Last day, YYYY-MM-DD. Defaults to 7 days after start_date."),
    ] = None,
    min_market_cap: Annotated[
        float | None,
        Field(
            description="Only companies at or above this market cap in USD (e.g., 10000000000 for $10B)",
            ge=0,
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of companies to return (1-100)", ge=1, le=100
        ),
    ] = 50,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Every company reporting earnings in a date range, market-wide: symbol, company, market cap, event, date, timing (BMO before open / AMC after close), EPS estimate and, once reported, actual EPS and surprise %.

    Use for "who reports this week", building a catalyst watchlist, or checking which holdings report soon. Not for one stock's history: use get_earnings for that. Results are sorted by market cap, largest first.

    Returns Markdown by default, or JSON when response_format='json'. An empty range returns a short message.
    """
    try:
        if not hasattr(yf, "Calendars"):
            return "The earnings calendar needs yfinance 1.0 or newer. Run: pip install -U yfinance"
        start = (
            pd.Timestamp(start_date).date() if start_date else pd.Timestamp.now().date()
        )
        end = (
            pd.Timestamp(end_date).date() if end_date else start + pd.Timedelta(days=7)
        )
        if end < start:
            raise ToolError("end_date must be on or after start_date.")
        session = _get_session()
        kw = {"session": session} if session is not None else {}
        cal = yf.Calendars(start=start, end=end, **kw)
        df = cal.get_earnings_calendar(market_cap=min_market_cap, limit=limit)
        if df is None or df.empty:
            return f"No earnings found between {start} and {end}."
        if "Marketcap" in df.columns:
            df = df.sort_values("Marketcap", ascending=False, na_position="last")

        rows = []
        for sym, r in df.head(limit).iterrows():
            rows.append(
                {
                    "symbol": sym,
                    "company": r.get("Company"),
                    "marketCap": r.get("Marketcap"),
                    "event": r.get("Event Name"),
                    "date": _date(r.get("Event Start Date")),
                    "timing": r.get("Timing"),
                    "epsEstimate": r.get("EPS Estimate"),
                    "reportedEps": r.get("Reported EPS"),
                    "surprisePercent": r.get("Surprise(%)"),
                }
            )

        def _md():
            result = f"# Earnings Calendar: {start} to {end}\n\n"
            result += f"{len(rows)} companies, largest first.\n\n"
            result += (
                "| Date | Symbol | Company | Market Cap | Timing | EPS Est. | Reported | Surprise |\n"
                "|---|---|---|---|---|---|---|---|\n"
            )
            for r in rows:
                result += (
                    f"| {r['date']} | {r['symbol']} | {r['company']} | {format_large_number(r['marketCap'])} | "
                    f"{r['timing'] or '-'} | {_num(r['epsEstimate'])} | {_num(r['reportedEps'])} | "
                    f"{_num(r['surprisePercent'], '+.2f', '%')} |\n"
                )
            return truncate_response(
                result, "Lower the limit or narrow the date range."
            )

        def _js():
            payload = {
                "start": str(start),
                "end": str(end),
                "count": len(rows),
                "earnings": rows,
            }
            return truncate_json_response(
                _json(payload), "Lower the limit or narrow the date range."
            )

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("earnings calendar", start_date or "today", e)


@mcp.tool(
    structured_output=False,
    name="screen_stocks",
    annotations={
        "title": "Run a Yahoo Finance Stock Screener",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@structured(ScreenOut)
def screen_stocks(
    screener: Annotated[
        Screener,
        Field(
            description=(
                "Predefined Yahoo screener. Stocks: day_gainers, day_losers, most_actives, most_shorted_stocks, "
                "small_cap_gainers, aggressive_small_caps, growth_technology_stocks, undervalued_growth_stocks, "
                "undervalued_large_caps. ETFs: top_etfs_us, top_performing_etfs, technology_etfs, bond_etfs. "
                "Mutual funds: top_mutual_funds, solid_large_growth_funds, solid_midcap_growth_funds, "
                "conservative_foreign_funds, high_yield_bond, portfolio_anchors."
            )
        ),
    ],
    count: Annotated[
        int,
        Field(description="Number of results (1-100)", ge=1, le=100),
    ] = 25,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Run one of Yahoo Finance's predefined screeners and return the matching symbols with price, % change, volume relative to the 3-month average, market cap, trailing and forward P/E, and 52-week range.

    Use to discover candidates you don't have yet: today's movers, unusual volume, heavily shorted names, undervalued growth or large caps, or top ETFs and funds. Not for a symbol you already know (use get_stock_quote) and not for custom filters: only Yahoo's predefined screeners exist, so pick the closest one. Results are live and reorder through the trading day, so two calls minutes apart can differ. count takes the top N in the screener's own ranking; there is no paging. Follow up on a symbol with get_stock_quote, get_company_info or get_earnings.

    Returns Markdown by default, or JSON when response_format='json'.
    """
    try:
        session = _get_session()
        kw = {"session": session} if session is not None else {}
        res = yf.screen(screener.value, count=count, **kw) or {}
        quotes = (res.get("quotes") or [])[:count]
        if not quotes:
            return f"The '{screener.value}' screener returned no results right now."

        rows = []
        for q in quotes:
            vol = q.get("regularMarketVolume")
            avg = q.get("averageDailyVolume3Month")
            rows.append(
                {
                    "symbol": q.get("symbol"),
                    "name": q.get("longName") or q.get("shortName"),
                    "type": q.get("quoteType"),
                    "price": q.get("regularMarketPrice"),
                    "changePercent": q.get("regularMarketChangePercent"),
                    "volume": vol,
                    "relativeVolume": round(vol / avg, 2) if vol and avg else None,
                    "marketCap": q.get("marketCap"),
                    "trailingPE": q.get("trailingPE"),
                    "forwardPE": q.get("forwardPE"),
                    "fiftyTwoWeekLow": q.get("fiftyTwoWeekLow"),
                    "fiftyTwoWeekHigh": q.get("fiftyTwoWeekHigh"),
                    "exchange": q.get("fullExchangeName") or q.get("exchange"),
                }
            )

        def _md():
            result = f"# Screener: {res.get('title') or screener.value}\n\n"
            if res.get("description"):
                result += f"{res['description']}\n\n"
            result += (
                f"Showing {len(rows)} of {res.get('total', len(rows))} matches.\n\n"
            )
            result += (
                "| Symbol | Name | Price | Change | Rel. Vol | Market Cap | P/E | Fwd P/E | 52w Range |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
            )
            for r in rows:
                result += (
                    f"| {r['symbol']} | {r['name'] or ''} | {_num(r['price'])} | "
                    f"{_num(r['changePercent'], '+.2f', '%')} | {_num(r['relativeVolume'], '.2f', 'x')} | "
                    f"{format_large_number(r['marketCap'])} | {_num(r['trailingPE'])} | {_num(r['forwardPE'])} | "
                    f"{_num(r['fiftyTwoWeekLow'])} - {_num(r['fiftyTwoWeekHigh'])} |\n"
                )
            return truncate_response(result, "Lower the count.")

        def _js():
            payload = {
                "screener": screener.value,
                "title": res.get("title"),
                "total": res.get("total"),
                "count": len(rows),
                "results": rows,
            }
            return truncate_json_response(_json(payload), "Lower the count.")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("screener results", screener.value, e)


@mcp.tool(
    structured_output=False,
    name="get_fund_data",
    annotations={
        "title": "Get ETF or Mutual Fund Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(FundOut)
def get_fund_data(
    ticker: Annotated[
        str,
        Field(
            description="ETF or mutual fund symbol (e.g., 'SPY', 'QQQ', 'VTI', 'VFIAX')",
            min_length=1,
            max_length=10,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """What an ETF or mutual fund holds and costs: category and fund family, expense ratio and turnover against its category average, top holdings with weights, sector weightings, and asset-class split (stock, bond, cash).

    Use for "what's in SPY", fund overlap and concentration checks, or comparing fund costs. Not for individual stocks: use get_company_info for those.

    Returns Markdown by default, or JSON when response_format='json'. A symbol that is not a fund returns a short message.
    """
    ticker = _norm_ticker(ticker)
    try:
        fd = make_ticker(ticker).funds_data

        def safe(attr, default=None):
            try:
                value = getattr(fd, attr)
                return default if value is None else value
            except Exception:
                return default

        overview = safe("fund_overview", {})
        holdings = safe("top_holdings")
        if not overview and (holdings is None or holdings.empty):
            return f"No fund data available for {ticker}. It may be a stock rather than an ETF or mutual fund."

        description = safe("description", "")
        sectors = safe("sector_weightings", {})
        assets = safe("asset_classes", {})
        ops = safe("fund_operations")
        operations = {}
        if ops is not None and not ops.empty:
            for attr, row in ops.iterrows():
                vals = row.tolist()
                operations[str(attr)] = {
                    "fund": vals[0] if len(vals) > 0 else None,
                    "categoryAverage": vals[1] if len(vals) > 1 else None,
                }
        top = []
        if holdings is not None and not holdings.empty:
            for sym, row in holdings.iterrows():
                top.append(
                    {
                        "symbol": sym,
                        "name": row.get("Name"),
                        "weight": row.get("Holding Percent"),
                    }
                )

        def _md():
            result = f"# Fund Data: {ticker}\n\n"
            if overview:
                result += f"- **Category:** {overview.get('categoryName', 'N/A')}\n"
                result += f"- **Family:** {overview.get('family', 'N/A')}\n"
                result += f"- **Type:** {overview.get('legalType', 'N/A')}\n"
            er = operations.get("Annual Report Expense Ratio")
            if er and _num(er["fund"]) != "-":
                result += f"- **Expense ratio:** {er['fund'] * 100:.3f}%"
                if _num(er["categoryAverage"]) != "-":
                    result += f" (category average {er['categoryAverage'] * 100:.2f}%)"
                result += "\n"
            to = operations.get("Annual Holdings Turnover")
            if to and _num(to["fund"]) != "-":
                result += f"- **Turnover:** {to['fund'] * 100:.1f}%\n"
            if description:
                result += f"\n{description[:600]}\n"
            if top:
                result += (
                    "\n## Top Holdings\n\n| Symbol | Name | Weight |\n|---|---|---|\n"
                )
                for h in top:
                    w = h["weight"] * 100 if _num(h["weight"]) != "-" else None
                    result += (
                        f"| {h['symbol']} | {h['name']} | {_num(w, '.2f', '%')} |\n"
                    )
            if sectors:
                result += "\n## Sector Weightings\n\n"
                for k, v in sorted(sectors.items(), key=lambda kv: -(kv[1] or 0)):
                    if v:
                        result += (
                            f"- **{k.replace('_', ' ').title()}:** {v * 100:.1f}%\n"
                        )
            if assets:
                result += "\n## Asset Classes\n\n"
                for k, v in assets.items():
                    if v:
                        result += f"- **{k.replace('Position', '').title()}:** {v * 100:.1f}%\n"
            return truncate_response(result, "")

        def _js():
            payload = {
                "ticker": ticker,
                "overview": overview,
                "description": description,
                "operations": operations,
                "topHoldings": top,
                "sectorWeightings": sectors,
                "assetClasses": assets,
            }
            return truncate_json_response(_json(payload), "")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("fund data", ticker, e)


@mcp.tool(
    structured_output=False,
    name="get_sector_overview",
    annotations={
        "title": "Get Sector or Industry Overview",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@structured(SectorOut)
def get_sector_overview(
    sector: Annotated[
        SectorKey,
        Field(
            description=(
                "Sector key: basic-materials, communication-services, consumer-cyclical, consumer-defensive, "
                "energy, financial-services, healthcare, industrials, real-estate, technology, utilities"
            )
        ),
    ],
    industry: Annotated[
        str | None,
        Field(
            description=(
                "Optional industry key inside the sector (e.g., 'semiconductors', 'software-infrastructure'). "
                "Call once without it: the sector response lists every valid industry key."
            ),
            max_length=80,
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Rows per company list (1-50)", ge=1, le=50),
    ] = 10,
    response_format: Annotated[
        ResponseFormat,
        Field(
            description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
        ),
    ] = ResponseFormat.MARKDOWN,
) -> str:
    """Overview of a market sector, or of one industry inside it: description, company count, total market cap, market weight, and the largest companies with analyst rating. A sector also lists its industries with their keys and weights; an industry adds its top growth companies (growth estimate) and top performers (YTD return, target price).

    Use for sector rotation, "biggest semiconductor companies", finding peers for a stock, or exploring an industry before picking names. Call without industry first, then pass one of the returned industry keys.

    Returns Markdown by default, or JSON when response_format='json'. An unknown industry key returns a short message listing the valid ones.
    """
    try:
        session = _get_session()
        kw = {"session": session} if session is not None else {}
        sec = yf.Sector(sector.value, **kw)

        if industry:
            key = (
                industry.strip()
                .lower()
                .replace(" & ", "-")
                .replace(" - ", "-")
                .replace(" ", "-")
            )
            valid = list(sec.industries.index) if sec.industries is not None else []
            if valid and key not in valid:
                raise ToolError(
                    f"'{industry}' is not an industry in {sector.value}. Valid keys: "
                    + ", ".join(valid)
                )
            obj = yf.Industry(key, **kw)
            label = f"{obj.name} ({sec.name})"
            lists = {
                "topCompanies": _records(obj.top_companies, limit),
                "topGrowthCompanies": _records(obj.top_growth_companies, limit),
                "topPerformingCompanies": _records(obj.top_performing_companies, limit),
            }
        else:
            obj = sec
            label = sec.name
            lists = {
                "topCompanies": _records(sec.top_companies, limit),
                "industries": _records(sec.industries, 200),
            }

        overview = obj.overview or {}
        if not overview and not any(lists.values()):
            return f"No data available for {label}."

        def _md():
            result = f"# {'Industry' if industry else 'Sector'}: {label}\n\n"
            if overview.get("description"):
                result += f"{overview['description']}\n\n"
            if overview.get("companies_count") is not None:
                result += f"- **Companies:** {overview['companies_count']}\n"
            if overview.get("market_cap") is not None:
                result += (
                    f"- **Market cap:** {format_large_number(overview['market_cap'])}\n"
                )
            if _num(overview.get("market_weight")) != "-":
                result += (
                    f"- **Market weight:** {overview['market_weight'] * 100:.2f}%\n"
                )
            titles = {
                "topCompanies": "Largest Companies",
                "topGrowthCompanies": "Top Growth Companies",
                "topPerformingCompanies": "Top Performers",
                "industries": "Industries",
            }
            for k, rows in lists.items():
                if not rows:
                    continue
                result += f"\n## {titles[k]}\n\n"
                cols = list(rows[0].keys())
                result += "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
                for r in rows:
                    cells = [
                        _num(r[c], ".4g") if isinstance(r[c], float) else str(r[c])
                        for c in cols
                    ]
                    result += "| " + " | ".join(cells) + " |\n"
            return truncate_response(result, "Lower the limit.")

        def _js():
            payload = {
                "sector": sector.value,
                "industry": industry,
                "name": label,
                "overview": overview,
                **lists,
            }
            return truncate_json_response(_json(payload), "Lower the limit.")

        return _respond(response_format, _md, _js)

    except Exception as e:
        return _error("sector overview", industry or sector.value, e)


_publish_output_schemas()


# ============================================================================
# RUN SERVER
# ============================================================================


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yahoo-finance-mcp",
        description="Yahoo Finance MCP server (stdio by default).",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help=(
            "Serve over Streamable HTTP at http://HOST:PORT/mcp instead of "
            "stdio. Use this for clients that connect to a URL rather than "
            "spawning a process (n8n, remote agents)."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "Interface to bind in --http mode (default: 127.0.0.1). Use "
            "0.0.0.0 to accept connections from other containers on the host."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind in --http mode (default: 8000).",
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        metavar="HOST[:PORT]",
        help=(
            "Host header to accept in --http mode, repeatable. Only consulted "
            "when --host is not loopback. Defaults to localhost, 127.0.0.1 and "
            "host.docker.internal on the bound port."
        ),
    )
    parser.add_argument(
        "--stateful",
        action="store_true",
        help=(
            "Keep a session per client in --http mode. The default is "
            "stateless, which every tool call in this server is anyway and "
            "which survives clients that drop the Mcp-Session-Id header."
        ),
    )
    return parser


def main() -> None:
    """Run the MCP server over stdio, or over Streamable HTTP with --http."""
    args = _build_arg_parser().parse_args()

    if not args.http:
        mcp.run()
        return

    # Every tool here is a single request/response against Yahoo Finance with
    # nothing carried between calls, so a session buys nothing and costs
    # compatibility: a client that forgets Mcp-Session-Id gets a 400 mid-run.
    security = None
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        # The SDK only builds a DNS-rebinding allow-list for a loopback bind.
        # Binding wider without one would accept any Host header, so build it
        # around the host actually bound instead of switching protection off.
        hosts = args.allowed_host or [
            f"127.0.0.1:{args.port}",
            f"localhost:{args.port}",
            # the alias a container uses to reach a server on its host, which
            # is how n8n and other dockerised clients arrive
            f"host.docker.internal:{args.port}",
        ]
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[f"http://{h}" for h in hosts],
        )

    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        stateless_http=not args.stateful,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
