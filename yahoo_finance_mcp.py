"""
Yahoo Finance MCP Server

This MCP server provides tools to access financial market data from Yahoo Finance,
including stock prices, company information, financial statements, and market analysis.

Built with FastMCP and yfinance library.
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime, timedelta
import json
import yfinance as yf
import pandas as pd

# Initialize the MCP server
mcp = FastMCP("yahoo_finance_mcp")

# Constants
CHARACTER_LIMIT = 25000  # Maximum response size in characters

# ============================================================================
# ENUMS AND INPUT MODELS
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
            return f"${num/1e9:.2f}B"
        elif abs(num) >= 1e6:
            return f"${num/1e6:.2f}M"
        elif abs(num) >= 1e3:
            return f"${num/1e3:.2f}K"
        else:
            return f"${num:.2f}"
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: Any) -> str:
    """Format a value as a percentage."""
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{float(value)*100:.2f}%"
    except (ValueError, TypeError):
        return str(value)


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Convert a pandas DataFrame to markdown format."""
    if df.empty:
        return "No data available"
    
    # Limit rows
    if len(df) > max_rows:
        df = df.head(max_rows)
        truncated_msg = f"\n\n*Showing first {max_rows} rows of {len(df)} total*"
    else:
        truncated_msg = ""
    
    return df.to_markdown() + truncated_msg


def truncate_response(response: str, message: str = "") -> str:
    """Truncate response if it exceeds CHARACTER_LIMIT."""
    if len(response) <= CHARACTER_LIMIT:
        return response
    
    truncated = response[:CHARACTER_LIMIT]
    truncation_msg = f"\n\n⚠️ Response truncated at {CHARACTER_LIMIT} characters. {message}"
    return truncated + truncation_msg


# ============================================================================
# TOOL INPUT MODELS
# ============================================================================

class TickerInput(BaseModel):
    """Input model for single ticker operations."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    
    ticker: str = Field(
        ...,
        description="Stock ticker symbol (e.g., 'AAPL' for Apple, 'MSFT' for Microsoft, 'TSLA' for Tesla)",
        min_length=1,
        max_length=10
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )
    
    @field_validator('ticker')
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        """Convert ticker to uppercase."""
        return v.upper().strip()


class HistoricalPriceInput(BaseModel):
    """Input model for historical price data."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    
    ticker: str = Field(
        ...,
        description="Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')",
        min_length=1,
        max_length=10
    )
    period: Period = Field(
        default=Period.ONE_MONTH,
        description="Time period for historical data (e.g., '1mo' for 1 month, '1y' for 1 year)"
    )
    interval: Interval = Field(
        default=Interval.ONE_DAY,
        description="Data interval (e.g., '1d' for daily, '1h' for hourly)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )
    
    @field_validator('ticker')
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()


class MultiTickerInput(BaseModel):
    """Input model for multiple ticker operations."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    
    tickers: List[str] = Field(
        ...,
        description="List of stock ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])",
        min_items=1,
        max_items=20
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )
    
    @field_validator('tickers')
    @classmethod
    def uppercase_tickers(cls, v: List[str]) -> List[str]:
        return [ticker.upper().strip() for ticker in v]


class QuoteComparisonInput(BaseModel):
    """Input model for comparing multiple stock quotes."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    
    tickers: List[str] = Field(
        ...,
        description="List of stock ticker symbols to compare (e.g., ['AAPL', 'MSFT', 'GOOGL'])",
        min_items=2,
        max_items=10
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )
    
    @field_validator('tickers')
    @classmethod
    def uppercase_tickers(cls, v: List[str]) -> List[str]:
        return [ticker.upper().strip() for ticker in v]


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
        "openWorldHint": True
    }
)
async def get_stock_quote(params: TickerInput) -> str:
    """Get current stock quote with real-time price, volume, and market data.
    
    This tool retrieves the latest stock quote including current price, day's range,
    trading volume, market cap, and other key metrics for a given ticker symbol.
    
    Use this tool when:
    - User wants current/latest stock price
    - User asks "what's the price of [stock]"
    - User wants to know if market is open
    - User wants basic stock information
    
    Args:
        params (TickerInput): Contains:
            - ticker (str): Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')
            - response_format (ResponseFormat): 'markdown' or 'json'
    
    Returns:
        str: Current stock quote in requested format (markdown or JSON)
    
    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Formatted markdown with current price, volume, market cap, etc.
    """
    try:
        ticker_obj = yf.Ticker(params.ticker)
        info = ticker_obj.info
        
        # Get fast info for real-time data
        try:
            fast_info = ticker_obj.fast_info
            current_price = fast_info.get('lastPrice', safe_get(info, 'currentPrice'))
            previous_close = fast_info.get('previousClose', safe_get(info, 'previousClose'))
        except Exception:
            current_price = safe_get(info, 'currentPrice')
            previous_close = safe_get(info, 'previousClose')
        
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
        
        if params.response_format == ResponseFormat.MARKDOWN:
            # Format as markdown
            result = f"# {safe_get(info, 'longName', params.ticker)} ({params.ticker})\n\n"
            result += f"**Current Price:** {format_currency(current_price)}\n"
            
            if change != "N/A":
                change_symbol = "🔺" if change >= 0 else "🔻"
                result += f"**Change:** {change_symbol} {format_currency(change)} ({change_pct:.2f}%)\n"
            
            result += f"\n## Market Data\n"
            result += f"- **Previous Close:** {format_currency(previous_close)}\n"
            result += f"- **Open:** {format_currency(safe_get(info, 'open'))}\n"
            result += f"- **Day's Range:** {format_currency(safe_get(info, 'dayLow'))} - {format_currency(safe_get(info, 'dayHigh'))}\n"
            result += f"- **52 Week Range:** {format_currency(safe_get(info, 'fiftyTwoWeekLow'))} - {format_currency(safe_get(info, 'fiftyTwoWeekHigh'))}\n"
            result += f"- **Volume:** {safe_get(info, 'volume'):,}\n" if safe_get(info, 'volume') != "N/A" else f"- **Volume:** N/A\n"
            result += f"- **Avg Volume:** {safe_get(info, 'averageVolume'):,}\n" if safe_get(info, 'averageVolume') != "N/A" else f"- **Avg Volume:** N/A\n"
            result += f"- **Market Cap:** {format_large_number(safe_get(info, 'marketCap'))}\n"
            result += f"- **Beta:** {safe_get(info, 'beta')}\n"
            result += f"- **PE Ratio:** {safe_get(info, 'trailingPE')}\n"
            result += f"- **EPS:** {format_currency(safe_get(info, 'trailingEps'))}\n"
            result += f"- **Dividend Yield:** {format_percentage(safe_get(info, 'dividendYield'))}\n"
            
            result += f"\n## Company Info\n"
            result += f"- **Sector:** {safe_get(info, 'sector')}\n"
            result += f"- **Industry:** {safe_get(info, 'industry')}\n"
            result += f"- **Website:** {safe_get(info, 'website')}\n"
            
            return truncate_response(result, "Use get_company_info for more detailed information.")
        else:
            # JSON format
            result = {
                "ticker": params.ticker,
                "longName": safe_get(info, 'longName'),
                "currentPrice": current_price,
                "previousClose": previous_close,
                "change": change,
                "changePercent": change_pct,
                "open": safe_get(info, 'open'),
                "dayLow": safe_get(info, 'dayLow'),
                "dayHigh": safe_get(info, 'dayHigh'),
                "fiftyTwoWeekLow": safe_get(info, 'fiftyTwoWeekLow'),
                "fiftyTwoWeekHigh": safe_get(info, 'fiftyTwoWeekHigh'),
                "volume": safe_get(info, 'volume'),
                "averageVolume": safe_get(info, 'averageVolume'),
                "marketCap": safe_get(info, 'marketCap'),
                "beta": safe_get(info, 'beta'),
                "trailingPE": safe_get(info, 'trailingPE'),
                "trailingEps": safe_get(info, 'trailingEps'),
                "dividendYield": safe_get(info, 'dividendYield'),
                "sector": safe_get(info, 'sector'),
                "industry": safe_get(info, 'industry'),
                "website": safe_get(info, 'website')
            }
            return json.dumps(result, indent=2)
            
    except Exception as e:
        error_msg = f"Error fetching quote for {params.ticker}: {str(e)}\n\n"
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
        "openWorldHint": True
    }
)
async def get_historical_prices(params: HistoricalPriceInput) -> str:
    """Get historical stock price data with OHLCV (Open, High, Low, Close, Volume).
    
    This tool retrieves historical price data for technical analysis, charting,
    and trend analysis. Data includes Open, High, Low, Close prices and Volume.
    
    Use this tool when:
    - User wants to see price history/trends
    - User asks "how has [stock] performed over [time period]"
    - User wants data for charting or analysis
    - User wants to compare historical prices
    
    Args:
        params (HistoricalPriceInput): Contains:
            - ticker (str): Stock ticker symbol
            - period (Period): Time period ('1mo', '1y', '5y', etc.)
            - interval (Interval): Data interval ('1d', '1h', etc.)
            - response_format (ResponseFormat): 'markdown' or 'json'
    
    Returns:
        str: Historical price data in requested format
    
    Example:
        Input: {"ticker": "AAPL", "period": "1mo", "interval": "1d"}
        Output: Daily OHLCV data for the past month
    """
    try:
        ticker_obj = yf.Ticker(params.ticker)
        hist = ticker_obj.history(period=params.period.value, interval=params.interval.value)
        
        if hist.empty:
            return f"No historical data available for {params.ticker} with period={params.period.value} and interval={params.interval.value}"
        
        if params.response_format == ResponseFormat.MARKDOWN:
            result = f"# Historical Prices: {params.ticker}\n\n"
            result += f"**Period:** {params.period.value} | **Interval:** {params.interval.value}\n\n"
            result += f"**Date Range:** {hist.index[0].strftime('%Y-%m-%d')} to {hist.index[-1].strftime('%Y-%m-%d')}\n"
            result += f"**Total Records:** {len(hist)}\n\n"
            
            # Summary statistics
            result += "## Summary Statistics\n\n"
            result += f"- **Highest Close:** {format_currency(hist['Close'].max())} on {hist['Close'].idxmax().strftime('%Y-%m-%d')}\n"
            result += f"- **Lowest Close:** {format_currency(hist['Close'].min())} on {hist['Close'].idxmin().strftime('%Y-%m-%d')}\n"
            result += f"- **Average Close:** {format_currency(hist['Close'].mean())}\n"
            result += f"- **Average Volume:** {hist['Volume'].mean():,.0f}\n"
            
            # Calculate return
            if len(hist) > 1:
                start_price = hist['Close'].iloc[0]
                end_price = hist['Close'].iloc[-1]
                total_return = ((end_price - start_price) / start_price) * 100
                result += f"- **Total Return:** {total_return:.2f}%\n"
            
            result += "\n## Recent Data\n\n"
            # Show last 10 records
            recent_data = hist.tail(10).copy()
            recent_data.index = recent_data.index.strftime('%Y-%m-%d %H:%M')
            result += dataframe_to_markdown(recent_data)

            if len(hist) > 10:
                result += f"\n\n*Showing last 10 of {len(hist)} records. Request more data if needed or use JSON format for complete data.*"
            
            return truncate_response(result, "Request smaller time period or use JSON format for complete data.")
        else:
            # JSON format - return all data
            hist_dict = hist.reset_index().to_dict(orient='records')
            # Convert timestamps to strings
            for record in hist_dict:
                if 'Date' in record:
                    record['Date'] = record['Date'].isoformat()
                elif 'Datetime' in record:
                    record['Datetime'] = record['Datetime'].isoformat()
            
            result = {
                "ticker": params.ticker,
                "period": params.period.value,
                "interval": params.interval.value,
                "totalRecords": len(hist),
                "data": hist_dict
            }
            return truncate_response(json.dumps(result, indent=2), "Consider using a shorter period.")
            
    except Exception as e:
        error_msg = f"Error fetching historical prices for {params.ticker}: {str(e)}\n\n"
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
        "openWorldHint": True
    }
)
async def get_company_info(params: TickerInput) -> str:
    """Get comprehensive company information including business description, officers, and key statistics.
    
    This tool retrieves detailed company information including business summary,
    company officers, address, employee count, and comprehensive financial metrics.
    
    Use this tool when:
    - User wants to know "what does [company] do"
    - User asks about company leadership/executives
    - User wants detailed company background
    - User needs comprehensive financial statistics
    
    Args:
        params (TickerInput): Contains:
            - ticker (str): Stock ticker symbol
            - response_format (ResponseFormat): 'markdown' or 'json'
    
    Returns:
        str: Detailed company information in requested format
    
    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Full company profile with description, officers, statistics
    """
    try:
        ticker_obj = yf.Ticker(params.ticker)
        info = ticker_obj.info
        
        if params.response_format == ResponseFormat.MARKDOWN:
            result = f"# {safe_get(info, 'longName', params.ticker)} ({params.ticker})\n\n"
            
            # Business Summary
            result += "## Business Summary\n\n"
            summary = safe_get(info, 'longBusinessSummary', 'No description available')
            result += f"{summary}\n\n"
            
            # Company Details
            result += "## Company Details\n\n"
            result += f"- **Sector:** {safe_get(info, 'sector')}\n"
            result += f"- **Industry:** {safe_get(info, 'industry')}\n"
            result += f"- **Full Time Employees:** {safe_get(info, 'fullTimeEmployees'):,}\n" if safe_get(info, 'fullTimeEmployees') != "N/A" else f"- **Full Time Employees:** N/A\n"
            result += f"- **Website:** {safe_get(info, 'website')}\n"
            result += f"- **Address:** {safe_get(info, 'address1')}, {safe_get(info, 'city')}, {safe_get(info, 'state')} {safe_get(info, 'zip')}\n"
            result += f"- **Country:** {safe_get(info, 'country')}\n"
            result += f"- **Phone:** {safe_get(info, 'phone')}\n\n"
            
            # Company Officers
            officers = safe_get(info, 'companyOfficers', [])
            if officers and isinstance(officers, list):
                result += "## Key Executives\n\n"
                for officer in officers[:5]:  # Show top 5
                    name = officer.get('name', 'N/A')
                    title = officer.get('title', 'N/A')
                    pay = officer.get('totalPay')
                    result += f"- **{name}** - {title}"
                    if pay:
                        result += f" (Compensation: {format_large_number(pay)})"
                    result += "\n"
                result += "\n"
            
            # Key Statistics
            result += "## Key Statistics\n\n"
            result += f"- **Market Cap:** {format_large_number(safe_get(info, 'marketCap'))}\n"
            result += f"- **Enterprise Value:** {format_large_number(safe_get(info, 'enterpriseValue'))}\n"
            result += f"- **PE Ratio (Trailing):** {safe_get(info, 'trailingPE')}\n"
            result += f"- **PE Ratio (Forward):** {safe_get(info, 'forwardPE')}\n"
            result += f"- **PEG Ratio:** {safe_get(info, 'pegRatio')}\n"
            result += f"- **Price to Book:** {safe_get(info, 'priceToBook')}\n"
            result += f"- **Price to Sales:** {safe_get(info, 'priceToSalesTrailing12Months')}\n"
            result += f"- **EPS (Trailing):** {format_currency(safe_get(info, 'trailingEps'))}\n"
            result += f"- **EPS (Forward):** {format_currency(safe_get(info, 'forwardEps'))}\n"
            result += f"- **Dividend Rate:** {format_currency(safe_get(info, 'dividendRate'))}\n"
            result += f"- **Dividend Yield:** {format_percentage(safe_get(info, 'dividendYield'))}\n"
            result += f"- **Ex-Dividend Date:** {safe_get(info, 'exDividendDate')}\n"
            result += f"- **Beta:** {safe_get(info, 'beta')}\n"
            result += f"- **52 Week High:** {format_currency(safe_get(info, 'fiftyTwoWeekHigh'))}\n"
            result += f"- **52 Week Low:** {format_currency(safe_get(info, 'fiftyTwoWeekLow'))}\n"
            result += f"- **50 Day Avg:** {format_currency(safe_get(info, 'fiftyDayAverage'))}\n"
            result += f"- **200 Day Avg:** {format_currency(safe_get(info, 'twoHundredDayAverage'))}\n"
            result += f"- **Shares Outstanding:** {safe_get(info, 'sharesOutstanding'):,}\n" if safe_get(info, 'sharesOutstanding') != "N/A" else f"- **Shares Outstanding:** N/A\n"
            result += f"- **Float Shares:** {safe_get(info, 'floatShares'):,}\n" if safe_get(info, 'floatShares') != "N/A" else f"- **Float Shares:** N/A\n"
            
            # Financial Highlights
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
            # JSON format - return full info dict
            return truncate_response(json.dumps(info, indent=2, default=str), "")
            
    except Exception as e:
        error_msg = f"Error fetching company info for {params.ticker}: {str(e)}\n\n"
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
        "openWorldHint": True
    }
)
async def get_financial_statements(params: TickerInput) -> str:
    """Get comprehensive financial statements including income statement, balance sheet, and cash flow.
    
    This tool retrieves all three major financial statements with quarterly and annual data.
    Essential for fundamental analysis and understanding company financials.
    
    Use this tool when:
    - User wants to see revenue, earnings, expenses
    - User asks about balance sheet items (assets, liabilities)
    - User wants cash flow information
    - User needs data for financial analysis
    
    Args:
        params (TickerInput): Contains:
            - ticker (str): Stock ticker symbol
            - response_format (ResponseFormat): 'markdown' or 'json'
    
    Returns:
        str: Financial statements in requested format
    
    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Income statement, balance sheet, and cash flow data
    """
    try:
        ticker_obj = yf.Ticker(params.ticker)
        
        # Get financial statements
        income_stmt = ticker_obj.income_stmt
        balance_sheet = ticker_obj.balance_sheet
        cash_flow = ticker_obj.cashflow
        
        if params.response_format == ResponseFormat.MARKDOWN:
            result = f"# Financial Statements: {params.ticker}\n\n"
            
            # Income Statement
            if not income_stmt.empty:
                result += "## Income Statement (Annual)\n\n"
                result += dataframe_to_markdown(income_stmt, max_rows=30)
                result += "\n\n"
            
            # Balance Sheet
            if not balance_sheet.empty:
                result += "## Balance Sheet (Annual)\n\n"
                result += dataframe_to_markdown(balance_sheet, max_rows=30)
                result += "\n\n"
            
            # Cash Flow Statement
            if not cash_flow.empty:
                result += "## Cash Flow Statement (Annual)\n\n"
                result += dataframe_to_markdown(cash_flow, max_rows=30)
                result += "\n\n"
            
            result += "*Note: Use JSON format for quarterly statements or complete data export.*"
            
            return truncate_response(result, "Request specific statement types separately if needed.")
        else:
            # JSON format
            result = {
                "ticker": params.ticker,
                "incomeStatement": income_stmt.to_dict() if not income_stmt.empty else {},
                "balanceSheet": balance_sheet.to_dict() if not balance_sheet.empty else {},
                "cashFlow": cash_flow.to_dict() if not cash_flow.empty else {}
            }
            return truncate_response(json.dumps(result, indent=2, default=str), "")
            
    except Exception as e:
        error_msg = f"Error fetching financial statements for {params.ticker}: {str(e)}\n\n"
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
        "openWorldHint": True
    }
)
async def compare_stocks(params: QuoteComparisonInput) -> str:
    """Compare key metrics across multiple stocks side-by-side.
    
    This tool enables easy comparison of multiple stocks by showing key metrics
    in a side-by-side format for quick analysis and decision making.
    
    Use this tool when:
    - User wants to compare multiple stocks
    - User asks "which is better, [stock1] or [stock2]"
    - User wants to see relative performance
    - User needs comparison for investment decisions
    
    Args:
        params (QuoteComparisonInput): Contains:
            - tickers (List[str]): 2-10 ticker symbols to compare
            - response_format (ResponseFormat): 'markdown' or 'json'
    
    Returns:
        str: Comparison table in requested format
    
    Example:
        Input: {"tickers": ["AAPL", "MSFT", "GOOGL"], "response_format": "markdown"}
        Output: Side-by-side comparison table of key metrics
    """
    try:
        comparison_data = []
        
        for ticker in params.tickers:
            try:
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info
                
                data = {
                    "Ticker": ticker,
                    "Name": safe_get(info, 'longName', ticker),
                    "Price": safe_get(info, 'currentPrice'),
                    "Change%": safe_get(info, 'regularMarketChangePercent'),
                    "MarketCap": safe_get(info, 'marketCap'),
                    "PE": safe_get(info, 'trailingPE'),
                    "EPS": safe_get(info, 'trailingEps'),
                    "DivYield%": safe_get(info, 'dividendYield'),
                    "Beta": safe_get(info, 'beta'),
                    "52WkHigh": safe_get(info, 'fiftyTwoWeekHigh'),
                    "52WkLow": safe_get(info, 'fiftyTwoWeekLow'),
                    "Volume": safe_get(info, 'volume'),
                    "AvgVolume": safe_get(info, 'averageVolume'),
                    "Sector": safe_get(info, 'sector'),
                    "Industry": safe_get(info, 'industry')
                }
                comparison_data.append(data)
            except Exception as e:
                comparison_data.append({
                    "Ticker": ticker,
                    "Error": str(e)
                })
        
        if params.response_format == ResponseFormat.MARKDOWN:
            result = f"# Stock Comparison: {', '.join(params.tickers)}\n\n"
            
            # Create comparison DataFrame
            df = pd.DataFrame(comparison_data)
            result += dataframe_to_markdown(df)
            
            result += "\n\n## Key Insights\n\n"
            
            # Find best/worst performers
            valid_data = [d for d in comparison_data if "Error" not in d]
            if valid_data:
                # Highest price
                prices = [(d["Ticker"], d["Price"]) for d in valid_data if d["Price"] != "N/A"]
                if prices:
                    highest = max(prices, key=lambda x: x[1])
                    result += f"- **Highest Price:** {highest[0]} at {format_currency(highest[1])}\n"
                
                # Largest market cap
                market_caps = [(d["Ticker"], d["MarketCap"]) for d in valid_data if d["MarketCap"] != "N/A"]
                if market_caps:
                    largest = max(market_caps, key=lambda x: x[1])
                    result += f"- **Largest Market Cap:** {largest[0]} at {format_large_number(largest[1])}\n"
                
                # Best dividend yield
                div_yields = [(d["Ticker"], d["DivYield%"]) for d in valid_data if d["DivYield%"] != "N/A"]
                if div_yields:
                    best_div = max(div_yields, key=lambda x: x[1])
                    result += f"- **Highest Dividend Yield:** {best_div[0]} at {format_percentage(best_div[1])}\n"
            
            return truncate_response(result, "")
        else:
            # JSON format
            result = {
                "tickers": params.tickers,
                "comparison": comparison_data
            }
            return json.dumps(result, indent=2, default=str)
            
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
        "openWorldHint": True
    }
)
async def get_analyst_recommendations(params: TickerInput) -> str:
    """Get analyst recommendations, price targets, and upgrades/downgrades history.
    
    This tool provides Wall Street analyst consensus, price targets, and
    recommendation changes to help understand professional sentiment.
    
    Use this tool when:
    - User wants to know what analysts think
    - User asks about price targets or recommendations
    - User wants to see recent upgrades/downgrades
    - User needs professional analysis summary
    
    Args:
        params (TickerInput): Contains:
            - ticker (str): Stock ticker symbol
            - response_format (ResponseFormat): 'markdown' or 'json'
    
    Returns:
        str: Analyst recommendations and price targets
    
    Example:
        Input: {"ticker": "AAPL", "response_format": "markdown"}
        Output: Analyst consensus, price targets, recent recommendations
    """
    try:
        ticker_obj = yf.Ticker(params.ticker)
        recommendations = ticker_obj.recommendations
        info = ticker_obj.info
        
        if params.response_format == ResponseFormat.MARKDOWN:
            result = f"# Analyst Recommendations: {params.ticker}\n\n"
            
            # Price targets
            result += "## Price Targets\n\n"
            result += f"- **Target High:** {format_currency(safe_get(info, 'targetHighPrice'))}\n"
            result += f"- **Target Mean:** {format_currency(safe_get(info, 'targetMeanPrice'))}\n"
            result += f"- **Target Low:** {format_currency(safe_get(info, 'targetLowPrice'))}\n"
            result += f"- **Target Median:** {format_currency(safe_get(info, 'targetMedianPrice'))}\n"
            result += f"- **Current Price:** {format_currency(safe_get(info, 'currentPrice'))}\n\n"
            
            # Calculate upside/downside
            current = safe_get(info, 'currentPrice')
            target = safe_get(info, 'targetMeanPrice')
            if current != "N/A" and target != "N/A":
                upside = ((target - current) / current) * 100
                result += f"**Potential from Mean Target:** {upside:+.2f}%\n\n"
            
            # Analyst consensus
            result += "## Analyst Consensus\n\n"
            result += f"- **Number of Analysts:** {safe_get(info, 'numberOfAnalystOpinions')}\n"
            result += f"- **Recommendation Mean:** {safe_get(info, 'recommendationMean')} "
            
            rec_mean = safe_get(info, 'recommendationMean')
            if rec_mean != "N/A":
                if rec_mean <= 2.0:
                    result += "(Strong Buy/Buy)\n"
                elif rec_mean <= 3.0:
                    result += "(Hold)\n"
                else:
                    result += "(Sell/Underperform)\n"
            else:
                result += "\n"
            
            result += f"- **Recommendation Key:** {safe_get(info, 'recommendationKey')}\n\n"
            
            # Recent recommendations
            if recommendations is not None and not recommendations.empty:
                result += "## Recent Recommendations (Last 10)\n\n"
                recent = recommendations.tail(10).copy()
                recent.index = recent.index.strftime('%Y-%m-%d')
                result += dataframe_to_markdown(recent)
                if len(recommendations) > 10:
                    result += f"\n\n*Showing last 10 of {len(recommendations)} recommendations. Request more if needed.*"
            else:
                result += "No recent recommendation data available.\n"
            
            return truncate_response(result, "")
        else:
            # JSON format
            result = {
                "ticker": params.ticker,
                "priceTargets": {
                    "high": safe_get(info, 'targetHighPrice'),
                    "mean": safe_get(info, 'targetMeanPrice'),
                    "low": safe_get(info, 'targetLowPrice'),
                    "median": safe_get(info, 'targetMedianPrice'),
                    "currentPrice": safe_get(info, 'currentPrice')
                },
                "consensus": {
                    "numberOfAnalysts": safe_get(info, 'numberOfAnalystOpinions'),
                    "recommendationMean": safe_get(info, 'recommendationMean'),
                    "recommendationKey": safe_get(info, 'recommendationKey')
                },
                "recentRecommendations": recommendations.to_dict() if recommendations is not None and not recommendations.empty else {}
            }
            return json.dumps(result, indent=2, default=str)
            
    except Exception as e:
        error_msg = f"Error fetching analyst recommendations for {params.ticker}: {str(e)}\n\n"
        error_msg += "**Troubleshooting:**\n"
        error_msg += "- Verify ticker symbol is correct\n"
        error_msg += "- Analyst data may not be available for all stocks"
        return error_msg


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server with stdio transport (default for Claude Desktop)
    mcp.run()
