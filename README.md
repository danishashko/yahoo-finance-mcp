# Yahoo Finance MCP Server 📈

[![npm version](https://img.shields.io/npm/v/yahoo-finance-mcp-server.svg)](https://www.npmjs.com/package/yahoo-finance-mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that provides real-time stock market data through Yahoo Finance. Access stock quotes, historical prices, company information, financial statements, and analyst recommendations directly in Claude Desktop or any MCP-compatible client.

## 🎯 What Does This Do?

This MCP server gives your AI assistant real-time access to:
- 📊 **Real-time stock quotes** with market data
- 📈 **Historical price data** and performance metrics
- 🏢 **Company information** and business details
- 💰 **Financial statements** (income, balance sheet, cash flow)
- 🎯 **Analyst recommendations** and price targets
- ⚖️ **Multi-stock comparisons** side-by-side

## 🚀 Quick Start (npm)

### Install via npx (No installation required)

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

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

That's it! The server will auto-install Python dependencies on first run.

### Or install globally

```bash
npm install -g yahoo-finance-mcp-server

# Then use in Claude Desktop config:
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "yahoo-finance-mcp-server"
    }
  }
}
```

## 📋 Prerequisites

- **Python 3.10+** - [Download here](https://www.python.org/downloads/)
- **Node.js** (for npm installation)

## 🛠️ Manual Installation (Alternative)

If you prefer to install manually:

### Step 2: Download the Server File

1. Save the `yahoo_finance_mcp.py` file to a folder on your computer
2. Remember where you saved it (you'll need this path)

### Step 3: Configure Claude Desktop

To use this server with Claude Desktop, you need to add it to your configuration file.

#### On Mac:

1. Open Terminal
2. Type: `nano ~/Library/Application\ Support/Claude/claude_desktop_config.json`
3. Add the following configuration (adjust the path to where you saved the file):

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python3",
      "args": ["/path/to/yahoo_finance_mcp.py"]
    }
  }
}
```

4. Press `Ctrl + X`, then `Y`, then `Enter` to save

#### On Windows:

1. Open Notepad as Administrator
2. Open: `%APPDATA%\Claude\claude_desktop_config.json`
3. Add the following configuration (adjust the path):

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python",
      "args": ["C:\\path\\to\\yahoo_finance_mcp.py"]
    }
  }
}
```

4. Save the file

**Important:** Replace `/path/to/yahoo_finance_mcp.py` with the actual path where you saved the file!

### Step 4: Restart Claude Desktop

Close Claude Desktop completely and open it again. The Yahoo Finance tools should now be available!

## ✅ Testing the Installation

Once Claude Desktop restarts, try asking:

- "What's the current price of Apple stock?"
- "Show me Tesla's stock performance over the last year"
- "Compare Apple, Microsoft, and Google stocks"
- "What do analysts think about Amazon?"

If everything is working, Claude will use the Yahoo Finance tools to answer these questions!

## 🔧 Available Tools

The server provides these tools:

### 1. **get_stock_quote**
Get current price, volume, market cap, and basic info for a stock.

Example: "What's the price of AAPL?"

### 2. **get_historical_prices**
Get price history over different time periods (1 day to 10 years).

Example: "Show me Microsoft's stock price over the last 6 months"

### 3. **get_company_info**
Get detailed company information, officers, and comprehensive statistics.

Example: "Tell me about Tesla as a company"

### 4. **get_financial_statements**
Get income statement, balance sheet, and cash flow data.

Example: "Show me Apple's financial statements"

### 5. **compare_stocks**
Compare multiple stocks side-by-side.

Example: "Compare AAPL, MSFT, and GOOGL"

### 6. **get_analyst_recommendations**
Get Wall Street analyst ratings and price targets.

Example: "What do analysts think about Tesla?"

## 📊 Example Questions to Ask Claude

Here are some example questions you can ask once the server is running:

**Basic Quotes:**
- "What's the current stock price of Apple?"
- "How is Tesla stock doing today?"
- "Show me the quote for Microsoft"

**Historical Data:**
- "Show me Amazon's stock performance over the last year"
- "What was Google's stock price history in the last 3 months?"
- "Get me daily prices for Netflix over the past month"

**Company Information:**
- "Tell me about Apple's business"
- "Who are the executives at Microsoft?"
- "What sector is Tesla in?"

**Financial Analysis:**
- "Show me Apple's income statement"
- "What's Microsoft's revenue?"
- "Get Tesla's balance sheet"

**Comparisons:**
- "Compare Apple, Microsoft, and Google stocks"
- "Which is better: Tesla or Ford?"
- "Compare the tech giants"

**Analyst Insights:**
- "What do analysts think about Amazon?"
- "What's the price target for Tesla?"
- "Show me recent analyst recommendations for Apple"

## 🐛 Troubleshooting

### "Command not found" or "Python not found"

**Solution:** Make sure Python is installed and in your PATH. Try using `python3` instead of `python` in the config file (especially on Mac/Linux).

### "Module not found: yfinance" or "Module not found: mcp"

**Solution:** Install the required libraries:
```bash
pip install yfinance pandas mcp
```

Or on Mac/Linux:
```bash
pip3 install yfinance pandas mcp
```

### "No such file or directory"

**Solution:** Double-check the path in your `claude_desktop_config.json`. Make sure:
- The path is correct and complete
- On Windows, use double backslashes (`\\`) or forward slashes (`/`)
- The file actually exists at that location

### Tools not showing up in Claude

**Solution:**
1. Make sure you saved the config file correctly
2. Restart Claude Desktop completely (quit and reopen)
3. Check that the JSON syntax is correct (no missing commas or brackets)

### "Error fetching data" messages

**Solution:**
- Check your internet connection
- Verify the ticker symbol is correct (e.g., "AAPL" not "Apple")
- Some stocks may have limited data available
- Yahoo Finance API may be temporarily down

## 🔒 Privacy & Rate Limits

- This server uses the **free** Yahoo Finance API through the yfinance library
- All data requests go directly to Yahoo Finance - nothing is stored
- Yahoo Finance has rate limits (~2,000 requests/hour per IP)
- This is intended for **personal use only**, not commercial applications

## 📝 Notes

- Stock tickers should be in UPPERCASE (AAPL, MSFT, TSLA, etc.)
- Market data may have a 15-20 minute delay for some stocks
- Not all data is available for every stock (especially smaller companies)
- Financial statements are typically available for larger public companies

## 🆘 Getting Help

If you're having trouble:

1. Double-check you followed all installation steps
2. Make sure Python and all libraries are installed correctly
3. Verify your `claude_desktop_config.json` syntax is correct
4. Try the troubleshooting steps above

## 📚 Additional Resources

- [Python Download](https://www.python.org/downloads/)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [yfinance Documentation](https://ranaroussi.github.io/yfinance/)
- [Claude Desktop](https://claude.ai/download)

## ⚖️ Legal Disclaimer

This tool uses Yahoo Finance's publicly available data through the yfinance library. Yahoo!, Y!Finance, and Yahoo! Finance are registered trademarks of Yahoo, Inc. This tool is not affiliated with, endorsed by, or vetted by Yahoo, Inc.

Please refer to Yahoo!'s terms of use for details on your rights to use the data. This API is intended for personal, educational, and research purposes only.

## 🎉 You're All Set!

Once everything is configured, you can start asking Claude about stocks and financial data. Have fun exploring the markets! 📈

---

## 👤 Author

**Daniel Shashko**
- GitHub: [@danishashko](https://github.com/danishashko)
- LinkedIn: [daniel-shashko](https://linkedin.com/in/daniel-shashko)
- npm: [@danishashko](https://www.npmjs.com/~danishashko)

## 📄 License

MIT © Daniel Shashko
