# Yahoo Finance MCP Server 📈

[![npm version](https://img.shields.io/npm/v/yahoo-finance-mcp-server.svg)](https://www.npmjs.com/package/yahoo-finance-mcp-server)
[![npm downloads](https://img.shields.io/npm/dm/yahoo-finance-mcp-server.svg)](https://www.npmjs.com/package/yahoo-finance-mcp-server)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Real-time stock market data for Claude Desktop and any MCP-compatible client, powered by Yahoo Finance. Get quotes, historical prices, company profiles, financial statements, analyst ratings, and multi-stock comparisons, all from natural language.

> **npm package:** [`yahoo-finance-mcp-server`](https://www.npmjs.com/package/yahoo-finance-mcp-server) &nbsp;·&nbsp; **GitHub repo:** [`danishashko/yahoo-finance-mcp`](https://github.com/danishashko/yahoo-finance-mcp). The repo name is shorter than the package name; both refer to this project.

## 🎯 What You Get

- 📊 **Real-time stock quotes** with full market data
- 📈 **Historical prices** (OHLCV) with summary statistics
- 🏢 **Company profiles**, officers, and key statistics
- 💰 **Financial statements** (income, balance sheet, cash flow)
- 🎯 **Analyst ratings**, price targets, and the recent recommendation trend
- ⚖️ **Multi-stock comparisons** side by side
- 📰 **Latest financial news** per ticker
- 🧾 **Options chains** (calls/puts, strikes, IV, open interest)
- 🏦 **Ownership data** — institutional, mutual fund, and insider activity
- 💵 **Dividend & split history**
- 🔮 **Forward analyst estimates** (price targets, EPS/revenue, growth)
- 🔎 **Symbol search** by company name or keyword
- 🕒 **Market status** (open/closed) and index summary

Every tool returns human-readable **markdown** by default, or structured **JSON** on request (`response_format: "json"`). Requests share a single browser-impersonating HTTP session to reduce Yahoo Finance rate-limiting.

## 🚀 Quick Start

Add this to your Claude Desktop config and restart Claude:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "npx",
      "args": ["-y", "yahoo-finance-mcp-server"]
    }
  }
}
```

That is it. On first launch the npx wrapper creates an isolated Python environment and installs the dependencies for you (a one-time step that can take a minute). You only need **Python 3.10+** and **Node.js 16+** on your machine.

### Prefer a global install?

```bash
npm install -g yahoo-finance-mcp-server
```

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "yahoo-finance-mcp-server"
    }
  }
}
```

## 🔧 Available Tools

| Tool | What it returns | Parameters |
|------|-----------------|------------|
| `get_stock_quote` | Current price, change, day and 52-week range, volume, market cap, P/E, EPS, dividend yield | `ticker` |
| `get_historical_prices` | OHLCV history with summary stats and total return | `ticker`, `period`, `interval` |
| `get_company_info` | Business summary, key executives, valuation and financial highlights | `ticker` |
| `get_financial_statements` | Annual income statement, balance sheet, and cash flow | `ticker` |
| `compare_stocks` | Key metrics for multiple tickers side by side, plus quick insights | `tickers` (2 to 10) |
| `get_analyst_recommendations` | Price targets, consensus, recommendation trend, and recent upgrades/downgrades | `ticker` |
| `get_market_news` | Latest news headlines with source, date, summary, and link | `ticker`, `count` |
| `get_options_chain` | Expiration dates, or the calls/puts chain (strike, bid/ask, volume, OI, IV) | `ticker`, `expiration_date`, `option_type` |
| `get_holders` | Institutional, mutual-fund, or major holders, or insider transactions | `ticker`, `holder_type` |
| `get_dividends_splits` | Dividend payment history (with summary) and stock-split history | `ticker` |
| `get_analyst_estimates` | Forward price targets, EPS/revenue estimates by period, and growth estimates | `ticker` |
| `search_symbols` | Find ticker symbols by company name or keyword | `query`, `count` |
| `get_market_status` | Whether a market is open/closed, with timing and a major-index summary | `region` |

Every tool also accepts `response_format` (`"markdown"`, the default, or `"json"`).

**`get_historical_prices` options:**

- `period`: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`
- `interval`: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo`

**`get_options_chain`:** call without `expiration_date` to list available dates, then again with a date. `option_type` is `calls`, `puts`, or `both`.

**`get_holders`:** `holder_type` is `institutional`, `mutualfund`, `major`, or `insider_transactions`.

## 💬 Example Prompts

Once the server is connected, just ask Claude:

- "What's the current price of Apple stock?"
- "Show me Amazon's stock performance over the last year"
- "Tell me about Tesla as a company and who runs it"
- "Show me Apple's income statement"
- "Compare AAPL, MSFT, and GOOGL"
- "What do analysts think about Amazon, and what's the price target?"
- "What's the latest news on NVIDIA?"
- "Show me the SPY call options expiring next month"
- "Who are the biggest institutional holders of Apple?"
- "What's Coca-Cola's dividend history?"

## 🛠️ Manual Installation (Alternative)

If you would rather run the Python file directly instead of via npx:

**1. Download the server**

Save `yahoo_finance_mcp.py` somewhere on your machine and install the dependencies:

```bash
pip install yfinance curl_cffi pandas tabulate mcp pydantic httpx
```

(or `pip3` on macOS/Linux)

**2. Point Claude Desktop at it**

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python3",
      "args": ["/absolute/path/to/yahoo_finance_mcp.py"]
    }
  }
}
```

On Windows use `"command": "python"` and a path like `"C:\\path\\to\\yahoo_finance_mcp.py"` (double backslashes or forward slashes).

**3. Restart Claude Desktop.**

## 🐛 Troubleshooting

**"Command not found" / "Python not found"**
Make sure Python and Node.js are installed and on your PATH. On macOS/Linux, try `python3` instead of `python` in the config.

**"Module not found: yfinance" (manual install only)**
Install the dependencies:

```bash
pip install yfinance curl_cffi pandas tabulate mcp pydantic httpx
```

**Tools not showing up in Claude**
1. Confirm the config file is valid JSON (no trailing commas).
2. Fully quit and reopen Claude Desktop.
3. Check the path in your config actually exists.

**"Error fetching data"**
- Check your internet connection.
- Verify the ticker symbol (for example `AAPL`, not `Apple`).
- Some smaller companies have limited data, and Yahoo Finance can be briefly unavailable.

## 🔒 Privacy & Rate Limits

- Uses the free Yahoo Finance API via the `yfinance` library.
- Requests go straight to Yahoo Finance. Nothing is stored or proxied.
- Yahoo Finance rate-limits roughly 2,000 requests/hour per IP.
- Intended for personal, educational, and research use.

## 📝 Notes

- Use ticker symbols in uppercase (`AAPL`, `MSFT`, `TSLA`).
- Some quotes may be delayed 15 to 20 minutes.
- Financial statements are generally available for larger public companies.

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history. The core fixes (tool input validation, analyst recommendations, dividend yield, working `npx` install) landed in **v1.1.0**.

## 📚 Resources

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [yfinance documentation](https://ranaroussi.github.io/yfinance/)
- [Python downloads](https://www.python.org/downloads/)
- [Claude Desktop](https://claude.ai/download)

## ⚖️ Legal Disclaimer

This tool uses Yahoo Finance's publicly available data through the `yfinance` library. Yahoo!, Y!Finance, and Yahoo! Finance are registered trademarks of Yahoo, Inc. This tool is not affiliated with, endorsed by, or vetted by Yahoo, Inc. Please refer to Yahoo!'s terms of use for details on your rights to use the data.

## 👤 Author

**Daniel Shashko**
- GitHub: [@danishashko](https://github.com/danishashko)
- LinkedIn: [daniel-shashko](https://linkedin.com/in/daniel-shashko)
- npm: [danielshashko](https://www.npmjs.com/~danielshashko)

## 📄 License

MIT © Daniel Shashko
