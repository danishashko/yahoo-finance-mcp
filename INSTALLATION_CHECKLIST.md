# Yahoo Finance MCP Server - Installation Checklist

Use this checklist to track your progress setting up the server.

---

## ✅ Pre-Installation

- [ ] I have downloaded all the files from the package
- [ ] I have created a folder for the server (e.g., `yahoo-finance-mcp`)
- [ ] I have put all files in this folder
- [ ] I know where this folder is located on my computer

---

## ✅ Python Installation

- [ ] Python 3.8+ is installed on my computer
- [ ] I can run `python --version` (or `python3 --version`) successfully
- [ ] On Windows: I checked "Add Python to PATH" during installation
- [ ] I can run `pip --version` (or `pip3 --version`) successfully

**Verify:**
```bash
python --version
# OR
python3 --version
```

Should show: `Python 3.8.0` or higher

---

## ✅ Dependencies Installation

Choose ONE method:

### Method 1: Installation Script (Recommended)
- [ ] I ran `install.bat` (Windows) or `./install.sh` (Mac/Linux)
- [ ] I saw "Installation complete!" message
- [ ] No errors appeared during installation

### Method 2: Manual Installation
- [ ] I ran `pip install -r requirements.txt`
- [ ] I saw "Successfully installed" messages
- [ ] All packages installed without errors

**Verify:**
```bash
python test_installation.py
```

Should show: "🎉 All tests passed!"

---

## ✅ Find the Server File Path

- [ ] I know the FULL path to `yahoo_finance_mcp.py`
- [ ] I have written down or copied this path
- [ ] The path includes the filename (yahoo_finance_mcp.py)

**Examples:**
- Windows: `C:\Users\YourName\Documents\yahoo-finance-mcp\yahoo_finance_mcp.py`
- Mac: `/Users/YourName/Documents/yahoo-finance-mcp/yahoo_finance_mcp.py`
- Linux: `/home/yourname/Documents/yahoo-finance-mcp/yahoo_finance_mcp.py`

**My Path:**
```
_____________________________________________________________
```
(Write it here!)

---

## ✅ Claude Desktop Configuration

- [ ] I found where Claude Desktop's config file should be
  - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

- [ ] I opened the config file in a text editor
- [ ] I added the server configuration
- [ ] I replaced the placeholder path with MY actual path
- [ ] I used the correct slash format:
  - Windows: Double backslash `\\` OR forward slash `/`
  - Mac/Linux: Forward slash `/`

- [ ] My config file looks like this:

**Windows:**
```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python",
      "args": ["C:\\Users\\YourName\\Documents\\yahoo-finance-mcp\\yahoo_finance_mcp.py"]
    }
  }
}
```

**Mac/Linux:**
```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python3",
      "args": ["/Users/YourName/Documents/yahoo-finance-mcp/yahoo_finance_mcp.py"]
    }
  }
}
```

- [ ] I saved the config file
- [ ] No text editor warnings or errors when saving

---

## ✅ JSON Syntax Check

My config file has:
- [ ] Opening brace `{` at the start
- [ ] Closing brace `}` at the end
- [ ] All strings in double quotes `"like this"`
- [ ] Commas between items (but NOT after the last item)
- [ ] Square brackets `[` and `]` around the args array
- [ ] My actual path (not the example path)

---

## ✅ Restart Claude Desktop

- [ ] I completely QUIT Claude Desktop (not just closed the window)
  - Windows: Right-click system tray icon → Exit
  - Mac: Cmd+Q or right-click dock icon → Quit
  
- [ ] I waited 5-10 seconds
- [ ] I reopened Claude Desktop
- [ ] Claude Desktop started successfully

---

## ✅ Test the Server

I tried asking Claude:

- [ ] "What's the current price of Apple stock?"
- [ ] Claude responded with actual stock data
- [ ] No error messages appeared
- [ ] The response includes price information

If this worked: **🎉 SUCCESS! You're all done!**

If not, continue to troubleshooting...

---

## 🐛 Troubleshooting Checklist

If it's not working, check:

### Check 1: Python Installation
- [ ] Run: `python --version` (or `python3 --version`)
- [ ] Shows version 3.8 or higher?

### Check 2: Packages Installation
- [ ] Run: `python test_installation.py`
- [ ] All tests pass?

### Check 3: Config File Location
- [ ] Config file exists?
- [ ] In the correct location?
- [ ] Named exactly `claude_desktop_config.json`?

### Check 4: Config File Content
- [ ] Open config file again
- [ ] Path is EXACTLY correct?
- [ ] No typos in the path?
- [ ] File actually exists at that path?
- [ ] JSON syntax is valid?

### Check 5: File Permissions
- [ ] Can you open yahoo_finance_mcp.py in a text editor?
- [ ] File is not corrupted?

### Check 6: Claude Desktop
- [ ] Did you restart Claude Desktop?
- [ ] Did you fully quit (not just close)?
- [ ] Try restarting again

---

## 📝 Common Mistakes

Check if you made any of these common errors:

### Path Mistakes
- [ ] Used example path instead of actual path
- [ ] Missing the filename at the end
- [ ] Wrong slashes on Windows (use `\\` or `/`)
- [ ] Spaces in path not handled correctly

### Config File Mistakes
- [ ] Forgot double quotes around strings
- [ ] Extra comma after last item
- [ ] Missing brackets or braces
- [ ] Typo in "mcpServers" or "command" or "args"

### Python Mistakes
- [ ] Used `python` when should use `python3`
- [ ] Python not in PATH
- [ ] Packages not installed

---

## 🎯 Final Verification

Everything works if:
- [ ] Python is installed (version 3.8+)
- [ ] All packages are installed (yfinance, pandas, mcp, etc.)
- [ ] Config file exists with correct path
- [ ] Config file has valid JSON syntax
- [ ] Claude Desktop has been restarted
- [ ] Claude can answer stock questions

---

## 📚 Next Steps After Success

Once everything works:
- [ ] Read QUICK_REFERENCE.md for example questions
- [ ] Try different types of queries
- [ ] Experiment with the 6 different tools
- [ ] Learn about financial metrics
- [ ] Have fun exploring the markets!

---

## 🆘 Still Stuck?

If you've checked everything and it still doesn't work:

1. Start over from the beginning
2. Follow SETUP_GUIDE.md step by step
3. Don't skip any steps
4. Double-check the path in config file
5. Make sure config file syntax is EXACTLY right
6. Restart Claude Desktop after ANY config change

---

**Pro Tip:** The most common issue is an incorrect or misformatted path in the config file. Take your time to get that exactly right!

---

**Date Completed:** ________________

**Notes:**
```




```

---

*Save this file and check off items as you complete them!*
