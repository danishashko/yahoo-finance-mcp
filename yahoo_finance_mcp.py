#!/usr/bin/env python3
"""
Yahoo Finance MCP Server

This MCP server provides tools to access financial market data from Yahoo Finance,
including stock prices, company information, financial statements, and market analysis.

Built with FastMCP and yfinance.
"""

import json
import logging
from enum import Enum
from typing import Annotated, Any, Dict, List

import yfinance as yf
import pandas as pd
from pydantic import Field

from mcp.server.fastmcp import FastMCP

# Keep yfinance from emitting warnings/progress that could clutter the
# stderr stream of an MCP stdio server. The JSON-RPC channel is stdout only.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Initialize the MCP server
mcp = FastMCP("yahoo_finance_mcp")

# Constants
CHARACTER_LIMIT = 25000  # Maximum response size in characters


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


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def _norm_ticker(value: str) -> str:
    """Normalize a single ticker symbol."""
    return value.strip().upper()


def safe_get(data: Dict[str, Any], key: str, default: Any = "N/A") -> Any:
    """Safely get a value from a dictionary."""
    return data.get(key, default)


def format_currency(value: Any) -> str:
    """Format a value as currency."""
    if value is None or value == "N/A":
        return "N/A"
    try:
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
        df = df.head(max_rows)
        truncated_msg = f"\n\n*Showing first {max_rows} rows of {len(df)} total*"

    try:
        return df.to_markdown() + truncated_msg
    except ImportError:
        # tabulate not installed - degrade gracefully to a fenced plain table.
        return "```\n" + df.to_string() + "\n```" + truncated_msg


def truncate_response(response: str, message: str = "") -> str:
    """Truncate a (markdown/text) response if it exceeds CHARACTER_LIMIT."""
    if len(response) <= CHARACTER_LIMIT:
        return response

    truncated = response[:CHARACTER_LIMIT]
    truncation_msg = (
        f"\n\n⚠️ Response truncated at {CHARACTER_LIMIT} characters. {message}"
    )
    return truncated + truncation_msg


def truncate_json_response(payload: str, message: str = "") -> str:
    """Truncate a JSON payload while keeping the result valid JSON.

    Rather than slicing a JSON string mid-structure (which yields unparseable
    output), wrap an oversized payload in a small valid JSON envelope.
    """
    if len(payload) <= CHARACTER_LIMIT:
        return payload

    note = f"Response exceeded {CHARACTER_LIMIT} characters and was truncated. {message}".strip()
    return json.dumps(
        {"warning": note, "truncatedPreview": payload[:CHARACTER_LIMIT]},
        indent=2,
    )


# ============================================================================
# MCP TOOLS
# ============================================================================


@mcp.tool(
    name="get_stock_quote",
    annotations={
        "title": "Get Current Stock Quote",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_stock_quote(
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
    """Get current stock quote with real-time price, volume, and market data.

    This tool retrieves the latest stock quote including current price, day's range,
    trading volume, market cap, and other key metrics for a given ticker symbol.

    Use this tool when:
    - User wants current/latest stock price
    - User asks "what's the price of [stock]"
    - User wants basic stock information

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA').
        response_format: 'markdown' or 'json'.

    Returns:
        str: Current stock quote in requested format (markdown or JSON).

    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Formatted markdown with current price, volume, market cap, etc.
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info

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

        if response_format == ResponseFormat.MARKDOWN:
            result = f"# {safe_get(info, 'longName', ticker)} ({ticker})\n\n"
            result += f"**Current Price:** {format_currency(current_price)}\n"

            if change != "N/A":
                change_symbol = "🔺" if change >= 0 else "🔻"
                result += f"**Change:** {change_symbol} {format_currency(change)} ({change_pct:.2f}%)\n"

            result += "\n## Market Data\n"
            result += f"- **Previous Close:** {format_currency(previous_close)}\n"
            result += f"- **Open:** {format_currency(safe_get(info, 'open'))}\n"
            result += f"- **Day's Range:** {format_currency(safe_get(info, 'dayLow'))} - {format_currency(safe_get(info, 'dayHigh'))}\n"
            result += f"- **52 Week Range:** {format_currency(safe_get(info, 'fiftyTwoWeekLow'))} - {format_currency(safe_get(info, 'fiftyTwoWeekHigh'))}\n"
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
            result += f"- **EPS:** {format_currency(safe_get(info, 'trailingEps'))}\n"
            result += f"- **Dividend Yield:** {format_dividend_yield(safe_get(info, 'dividendYield'))}\n"

            result += "\n## Company Info\n"
            result += f"- **Sector:** {safe_get(info, 'sector')}\n"
            result += f"- **Industry:** {safe_get(info, 'industry')}\n"
            result += f"- **Website:** {safe_get(info, 'website')}\n"

            return truncate_response(
                result, "Use get_company_info for more detailed information."
            )
        else:
            result = {
                "ticker": ticker,
                "longName": safe_get(info, "longName"),
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
            return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Error fetching quote for {ticker}: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify the ticker symbol is correct\n"
        error_msg += "- Check if the market is open (some data may be delayed)\n"
        error_msg += "- Try again in a moment if it's a temporary issue"
        return error_msg


@mcp.tool(
    name="get_historical_prices",
    annotations={
        "title": "Get Historical Stock Prices",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_historical_prices(
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
    """Get historical stock price data with OHLCV (Open, High, Low, Close, Volume).

    This tool retrieves historical price data for technical analysis, charting,
    and trend analysis.

    Use this tool when:
    - User wants to see price history/trends
    - User asks "how has [stock] performed over [time period]"
    - User wants data for charting or analysis

    Args:
        ticker: Stock ticker symbol.
        period: Time period ('1mo', '1y', '5y', etc.).
        interval: Data interval ('1d', '1h', etc.).
        response_format: 'markdown' or 'json'.

    Returns:
        str: Historical price data in requested format.

    Example:
        Input: {"ticker": "AAPL", "period": "1mo", "interval": "1d"}
        Output: Daily OHLCV data for the past month
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period=period.value, interval=interval.value)

        if hist.empty:
            return f"No historical data available for {ticker} with period={period.value} and interval={interval.value}"

        if response_format == ResponseFormat.MARKDOWN:
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
                result += f"\n\n*Showing last 10 of {len(hist)} records. Request more data if needed or use JSON format for complete data.*"

            return truncate_response(
                result,
                "Request smaller time period or use JSON format for complete data.",
            )
        else:
            hist_dict = hist.reset_index().to_dict(orient="records")
            for record in hist_dict:
                if "Date" in record:
                    record["Date"] = record["Date"].isoformat()
                elif "Datetime" in record:
                    record["Datetime"] = record["Datetime"].isoformat()

            result = {
                "ticker": ticker,
                "period": period.value,
                "interval": interval.value,
                "totalRecords": len(hist),
                "data": hist_dict,
            }
            return truncate_json_response(
                json.dumps(result, indent=2, default=str),
                "Consider using a shorter period.",
            )

    except Exception as e:
        error_msg = f"Error fetching historical prices for {ticker}: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify ticker symbol is correct\n"
        error_msg += "- Some intervals may not be available for all periods\n"
        error_msg += "- Try a different period/interval combination"
        return error_msg


@mcp.tool(
    name="get_company_info",
    annotations={
        "title": "Get Detailed Company Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_company_info(
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
    """Get comprehensive company information including business description, officers, and key statistics.

    Use this tool when:
    - User wants to know "what does [company] do"
    - User asks about company leadership/executives
    - User wants detailed company background
    - User needs comprehensive financial statistics

    Args:
        ticker: Stock ticker symbol.
        response_format: 'markdown' or 'json'.

    Returns:
        str: Detailed company information in requested format.

    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Full company profile with description, officers, statistics
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info

        if response_format == ResponseFormat.MARKDOWN:
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
            result += f"- **EPS (Trailing):** {format_currency(safe_get(info, 'trailingEps'))}\n"
            result += f"- **EPS (Forward):** {format_currency(safe_get(info, 'forwardEps'))}\n"
            result += f"- **Dividend Rate:** {format_currency(safe_get(info, 'dividendRate'))}\n"
            result += f"- **Dividend Yield:** {format_dividend_yield(safe_get(info, 'dividendYield'))}\n"
            result += f"- **Ex-Dividend Date:** {safe_get(info, 'exDividendDate')}\n"
            result += f"- **Beta:** {safe_get(info, 'beta')}\n"
            result += f"- **52 Week High:** {format_currency(safe_get(info, 'fiftyTwoWeekHigh'))}\n"
            result += f"- **52 Week Low:** {format_currency(safe_get(info, 'fiftyTwoWeekLow'))}\n"
            result += f"- **50 Day Avg:** {format_currency(safe_get(info, 'fiftyDayAverage'))}\n"
            result += f"- **200 Day Avg:** {format_currency(safe_get(info, 'twoHundredDayAverage'))}\n"
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
            result += f"- **Revenue Per Share:** {format_currency(safe_get(info, 'revenuePerShare'))}\n"
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
        else:
            return truncate_json_response(
                json.dumps(info, indent=2, default=str),
                "Use markdown format for a summarized view.",
            )

    except Exception as e:
        error_msg = f"Error fetching company info for {ticker}: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify ticker symbol is correct\n"
        error_msg += "- Some data may not be available for all companies"
        return error_msg


@mcp.tool(
    name="get_financial_statements",
    annotations={
        "title": "Get Company Financial Statements",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_financial_statements(
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
    """Get comprehensive financial statements including income statement, balance sheet, and cash flow.

    Use this tool when:
    - User wants to see revenue, earnings, expenses
    - User asks about balance sheet items (assets, liabilities)
    - User wants cash flow information
    - User needs data for financial analysis

    Args:
        ticker: Stock ticker symbol.
        response_format: 'markdown' or 'json'.

    Returns:
        str: Financial statements in requested format.

    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Income statement, balance sheet, and cash flow data
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = yf.Ticker(ticker)

        income_stmt = ticker_obj.income_stmt
        balance_sheet = ticker_obj.balance_sheet
        cash_flow = ticker_obj.cashflow

        if response_format == ResponseFormat.MARKDOWN:
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
        else:
            result = {
                "ticker": ticker,
                "incomeStatement": income_stmt.to_dict()
                if income_stmt is not None and not income_stmt.empty
                else {},
                "balanceSheet": balance_sheet.to_dict()
                if balance_sheet is not None and not balance_sheet.empty
                else {},
                "cashFlow": cash_flow.to_dict()
                if cash_flow is not None and not cash_flow.empty
                else {},
            }
            return truncate_json_response(
                json.dumps(result, indent=2, default=str),
                "Use markdown format for a summarized view.",
            )

    except Exception as e:
        error_msg = f"Error fetching financial statements for {ticker}: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify ticker symbol is correct\n"
        error_msg += "- Financial statements may not be available for all companies\n"
        error_msg += "- Try get_company_info for basic financial metrics"
        return error_msg


@mcp.tool(
    name="compare_stocks",
    annotations={
        "title": "Compare Multiple Stocks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def compare_stocks(
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
    """Compare key metrics across multiple stocks side-by-side.

    Use this tool when:
    - User wants to compare multiple stocks
    - User asks "which is better, [stock1] or [stock2]"
    - User wants to see relative performance

    Args:
        tickers: 2-10 ticker symbols to compare.
        response_format: 'markdown' or 'json'.

    Returns:
        str: Comparison table in requested format.

    Example:
        Input: {"tickers": ["AAPL", "MSFT", "GOOGL"], "response_format": "markdown"}
        Output: Side-by-side comparison table of key metrics
    """
    tickers = [_norm_ticker(t) for t in tickers]
    try:
        comparison_data = []

        for ticker in tickers:
            try:
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info

                data = {
                    "Ticker": ticker,
                    "Name": safe_get(info, "longName", ticker),
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

        if response_format == ResponseFormat.MARKDOWN:
            result = f"# Stock Comparison: {', '.join(tickers)}\n\n"

            df = pd.DataFrame(comparison_data)
            result += dataframe_to_markdown(df)

            result += "\n\n## Key Insights\n\n"

            valid_data = [d for d in comparison_data if "Error" not in d]
            if valid_data:

                def _numeric(items):
                    return [(t, v) for t, v in items if isinstance(v, (int, float))]

                prices = _numeric((d["Ticker"], d["Price"]) for d in valid_data)
                if prices:
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
        else:
            result = {"tickers": tickers, "comparison": comparison_data}
            return truncate_json_response(json.dumps(result, indent=2, default=str), "")

    except Exception as e:
        error_msg = f"Error comparing stocks: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify all ticker symbols are correct\n"
        error_msg += "- Some data may be missing for certain stocks"
        return error_msg


@mcp.tool(
    name="get_analyst_recommendations",
    annotations={
        "title": "Get Analyst Recommendations and Price Targets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_analyst_recommendations(
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
    """Get analyst recommendations, price targets, and the recent rating trend.

    Use this tool when:
    - User wants to know what analysts think
    - User asks about price targets or recommendations
    - User wants to see recent upgrades/downgrades
    - User needs a professional analysis summary

    Args:
        ticker: Stock ticker symbol.
        response_format: 'markdown' or 'json'.

    Returns:
        str: Analyst recommendations and price targets.

    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Analyst consensus, price targets, recommendation trend
    """
    ticker = _norm_ticker(ticker)
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info

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

        if response_format == ResponseFormat.MARKDOWN:
            result = f"# Analyst Recommendations: {ticker}\n\n"

            result += "## Price Targets\n\n"
            result += f"- **Target High:** {format_currency(safe_get(info, 'targetHighPrice'))}\n"
            result += f"- **Target Mean:** {format_currency(safe_get(info, 'targetMeanPrice'))}\n"
            result += f"- **Target Low:** {format_currency(safe_get(info, 'targetLowPrice'))}\n"
            result += f"- **Target Median:** {format_currency(safe_get(info, 'targetMedianPrice'))}\n"
            result += f"- **Current Price:** {format_currency(safe_get(info, 'currentPrice'))}\n\n"

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
        else:
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
                "upgradesDowngrades": upgrades.reset_index().to_dict(orient="records")
                if upgrades is not None and not upgrades.empty
                else [],
            }
            return truncate_json_response(json.dumps(result, indent=2, default=str), "")

    except Exception as e:
        error_msg = f"Error fetching analyst recommendations for {ticker}: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify ticker symbol is correct\n"
        error_msg += "- Analyst data may not be available for all stocks"
        return error_msg


# ============================================================================
# RUN SERVER
# ============================================================================


def main() -> None:
    """Run the MCP server with stdio transport (default for Claude Desktop)."""
    mcp.run()


if __name__ == "__main__":
    main()
