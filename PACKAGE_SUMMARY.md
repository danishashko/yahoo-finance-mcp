# Yahoo Finance MCP Server - Complete Package

## 📦 What's Included

This package contains everything you need to set up a Yahoo Finance MCP server for Claude Desktop, even if you're not a developer!

---

## 📄 Files Included

### 1. **yahoo_finance_mcp.py** ⭐ (MAIN FILE)
The MCP server that provides Yahoo Finance tools to Claude. This is the heart of the system.

**What it does:**
- Connects to Yahoo Finance API
- Provides 6 powerful tools for stock research
- Formats data in easy-to-read formats
- Handles errors gracefully

**Tools included:**
- `get_stock_quote` - Current prices and quotes
- `get_historical_prices` - Price history and charts
- `get_company_info` - Company details and officers
- `get_financial_statements` - Income, balance sheet, cash flow
- `compare_stocks` - Side-by-side comparisons
- `get_analyst_recommendations` - Wall Street analysis

### 2. **README.md** 📖
Complete documentation with installation instructions, usage examples, and troubleshooting.

**Sections:**
- What the server does
- Installation steps
- Configuration guide
- Available tools
- Example questions
- Troubleshooting
- Legal disclaimer

### 3. **SETUP_GUIDE.md** 🎯 (START HERE!)
Step-by-step visual guide for beginners. This is the best place to start if you're new to this!

**Includes:**
- Python installation instructions
- Detailed configuration steps
- Screenshots placeholders
- Common issues and solutions
- Success checklist

### 4. **QUICK_REFERENCE.md** 💡
Quick reference with popular ticker symbols and example queries.

**Contains:**
- 100+ ticker symbols by category
- 30+ example questions
- Tips for better results
- Metric explanations
- Follow-up suggestions

### 5. **requirements.txt** 📋
List of Python packages needed for the server.

**Packages:**
- yfinance - Yahoo Finance data library
- pandas - Data manipulation
- mcp - Model Context Protocol SDK
- pydantic - Data validation
- httpx - HTTP client

### 6. **install.sh** 🐧 (For Mac/Linux)
Automatic installation script for Mac and Linux users.

**What it does:**
- Checks if Python is installed
- Installs all required packages
- Shows success/error messages

### 7. **install.bat** 🪟 (For Windows)
Automatic installation script for Windows users.

**What it does:**
- Checks if Python is installed
- Installs all required packages
- Shows success/error messages

### 8. **claude_desktop_config_example.json** ⚙️
Example configuration file for Claude Desktop.

**Use this to:**
- See the correct JSON format
- Copy and modify with your path
- Troubleshoot config issues

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install Python
- Download from https://www.python.org/downloads/
- On Windows: Check "Add to PATH"
- Verify: `python --version` or `python3 --version`

### Step 2: Install Dependencies
**Easy way:**
- Windows: Double-click `install.bat`
- Mac/Linux: Run `./install.sh` in Terminal

**Manual way:**
```bash
pip install -r requirements.txt
```

### Step 3: Configure Claude Desktop
1. Edit `claude_desktop_config.json` (see SETUP_GUIDE.md for location)
2. Add your server configuration
3. Restart Claude Desktop
4. Start asking about stocks!

---

## 🎯 Recommended Reading Order

If you're new to this:

1. **SETUP_GUIDE.md** - Read this first! Complete walkthrough
2. **README.md** - General overview and documentation
3. **QUICK_REFERENCE.md** - Examples and tips once it's working

If you're experienced with Python/MCP:

1. **README.md** - Quick overview
2. Install dependencies from **requirements.txt**
3. Configure and run!

---

## 💻 System Requirements

**Operating System:**
- Windows 10/11
- macOS 10.14+
- Linux (any modern distribution)

**Software:**
- Python 3.8 or higher
- Claude Desktop app
- Internet connection

**Disk Space:**
- ~100 MB for Python packages
- Minimal for server files

**Skills Required:**
- None! This guide assumes no technical knowledge
- Can copy/paste and follow instructions? You're good!

---

## 🔧 What the Server Does

This MCP server acts as a bridge between Claude and Yahoo Finance. When you ask Claude about stocks:

1. Claude recognizes you want stock data
2. Claude calls one of the server's tools
3. The server fetches data from Yahoo Finance
4. The server formats the data nicely
5. Claude shows you the results

**You get:**
- Real-time stock prices
- Historical data and trends
- Company information
- Financial statements
- Analyst recommendations
- Much more!

---

## 🎓 Learning Path

### Day 1: Setup
- Install Python
- Install dependencies
- Configure Claude Desktop
- Test with basic queries

### Day 2: Explore
- Try different types of questions
- Learn about the 6 tools
- Understand the data
- Practice with various stocks

### Day 3: Master
- Compare multiple stocks
- Analyze financial statements
- Use advanced queries
- Understand financial metrics

---

## 📚 Additional Resources

**Official Documentation:**
- [Python.org](https://www.python.org/) - Python documentation
- [yfinance Docs](https://ranaroussi.github.io/yfinance/) - Yahoo Finance library
- [MCP Protocol](https://modelcontextprotocol.io/) - Model Context Protocol

**Learning Finance:**
- Investopedia - Financial education
- Yahoo Finance - Market news
- SEC.gov - Company filings

---

## ⚖️ Important Legal Notes

**Data Usage:**
- This uses Yahoo Finance's public API
- For personal, educational use only
- Not for commercial applications
- Subject to Yahoo's terms of service

**Not Financial Advice:**
- This tool provides data, not recommendations
- Always do your own research
- Past performance doesn't guarantee future results
- Consult financial professionals for advice

**No Warranties:**
- Data may be delayed or incorrect
- Yahoo Finance API may change
- Use at your own risk

---

## 🐛 Common Issues (Quick Reference)

| Issue | Solution |
|-------|----------|
| Python not found | Install from python.org, check PATH |
| Module not found | Run `pip install -r requirements.txt` |
| Config error | Check JSON syntax, verify path |
| Tools not showing | Restart Claude Desktop completely |
| Wrong data | Verify ticker symbol is correct |
| API errors | Check internet, try again later |

See SETUP_GUIDE.md for detailed troubleshooting!

---

## 🎉 What You'll Be Able To Do

Once set up, you can ask Claude:

**Basic:**
- "What's Apple's stock price?"
- "How is Tesla doing?"

**Advanced:**
- "Compare the FAANG stocks on key metrics"
- "Show me Microsoft's revenue growth over 5 years"
- "What do analysts think about Amazon?"

**Complex:**
- "Analyze Apple's financial health and compare it with Samsung"
- "Which tech stock has the best value based on PE ratio?"
- "Show me dividend-paying tech stocks"

---

## 📞 Support

**For setup help:**
- Read SETUP_GUIDE.md carefully
- Check the troubleshooting section
- Verify each step was completed

**For usage help:**
- Check QUICK_REFERENCE.md for examples
- Try rephrasing your question
- Ask Claude: "How do I find [information]?"

**For technical issues:**
- Verify Python installation
- Check all packages are installed
- Confirm config file is correct
- Test with simple queries first

---

## 🔄 Updates and Maintenance

**The server:**
- No updates needed - it's feature-complete!
- Yahoo Finance API may change over time
- Python packages can be updated with: `pip install --upgrade -r requirements.txt`

**If something breaks:**
- Check if yfinance needs updating
- Verify Yahoo Finance API is still available
- Check Claude Desktop hasn't changed config format

---

## ✨ Final Notes

This MCP server was built following best practices from the MCP builder skill, ensuring:
- ✅ High-quality, well-documented code
- ✅ Proper error handling
- ✅ User-friendly responses
- ✅ Comprehensive tool coverage
- ✅ Beginner-friendly setup

**The server provides:**
- 6 powerful financial research tools
- Real-time and historical data
- Multiple output formats (Markdown & JSON)
- Educational error messages
- Extensive documentation

---

## 🎊 You're Ready!

You now have everything needed to set up your Yahoo Finance MCP server. Take your time with the setup, follow SETUP_GUIDE.md, and soon you'll be asking Claude about stocks like a pro!

**Remember:**
- Be patient with the setup
- Follow the guide step by step
- Test with simple queries first
- Have fun exploring the markets!

Happy investing! 📈✨

---

*Last updated: October 2025*
*Built with ❤️ using the MCP Builder Skill*
