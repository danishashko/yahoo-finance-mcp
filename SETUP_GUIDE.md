# Yahoo Finance MCP Server - Step-by-Step Setup Guide

This guide will walk you through every step of setting up your Yahoo Finance MCP server, even if you're not a developer!

---

## 📱 What You'll Need

- A computer (Windows, Mac, or Linux)
- Claude Desktop app installed
- About 10 minutes of time
- Internet connection

---

## Part 1: Install Python (If Not Already Installed)

### Windows:

1. Go to https://www.python.org/downloads/
2. Click the big yellow "Download Python" button
3. Run the installer
4. **IMPORTANT:** Check the box "Add Python to PATH" at the bottom
5. Click "Install Now"
6. Wait for installation to complete
7. Click "Close"

### Mac:

1. Open Terminal (press Cmd + Space, type "Terminal")
2. Type: `python3 --version`
3. If you see a version number, Python is already installed!
4. If not, download from https://www.python.org/downloads/

### Verify Installation:

**Windows:**
- Press `Win + R`
- Type `cmd` and press Enter
- Type: `python --version`
- You should see something like: `Python 3.9.0`

**Mac:**
- Open Terminal
- Type: `python3 --version`
- You should see something like: `Python 3.9.0`

---

## Part 2: Download the Server Files

1. Download all the files you received:
   - `yahoo_finance_mcp.py` (the main server)
   - `requirements.txt` (list of dependencies)
   - `install.sh` or `install.bat` (installation script)
   - `README.md` (documentation)
   - `QUICK_REFERENCE.md` (examples)
   - `claude_desktop_config_example.json` (config template)

2. Create a new folder on your computer called `yahoo-finance-mcp`

3. Put all the downloaded files in this folder

4. Remember where this folder is! You'll need the full path later.
   - **Windows example:** `C:\Users\YourName\Documents\yahoo-finance-mcp`
   - **Mac example:** `/Users/YourName/Documents/yahoo-finance-mcp`

---

## Part 3: Install Required Libraries

### Option A: Using the Installation Script (Easier)

**On Windows:**
1. Navigate to your `yahoo-finance-mcp` folder
2. Double-click `install.bat`
3. A black window will appear and install everything
4. Wait for it to say "Installation complete!"
5. Press any key to close the window

**On Mac:**
1. Open Terminal
2. Type: `cd ` (with a space after cd)
3. Drag your `yahoo-finance-mcp` folder into the Terminal window
4. Press Enter
5. Type: `./install.sh`
6. Press Enter
7. Wait for "Installation complete!"

### Option B: Manual Installation

If the script doesn't work, do this instead:

**On Windows (Command Prompt):**
```
cd C:\Users\YourName\Documents\yahoo-finance-mcp
pip install -r requirements.txt
```

**On Mac (Terminal):**
```
cd /Users/YourName/Documents/yahoo-finance-mcp
pip3 install -r requirements.txt
```

Wait for all packages to install. You should see green "Successfully installed" messages.

---

## Part 4: Configure Claude Desktop

This is the most important part! We need to tell Claude Desktop where to find your server.

### Step 4.1: Find the Config File Location

**On Mac:**
- The config file is at: `~/Library/Application Support/Claude/claude_desktop_config.json`

**On Windows:**
- The config file is at: `%APPDATA%\Claude\claude_desktop_config.json`
- Which usually means: `C:\Users\YourName\AppData\Roaming\Claude\claude_desktop_config.json`

### Step 4.2: Edit the Config File

**On Mac:**

1. Open Terminal
2. Type: `nano ~/Library/Application\ Support/Claude/claude_desktop_config.json`
3. You'll see a text editor open
4. If the file is empty or has `{}`, replace everything with:

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

5. **IMPORTANT:** Replace `/Users/YourName/Documents/yahoo-finance-mcp/yahoo_finance_mcp.py` with YOUR actual path!
6. Press `Ctrl + X`
7. Press `Y`
8. Press `Enter`

**On Windows:**

1. Press `Win + R`
2. Type: `%APPDATA%\Claude`
3. Press Enter
4. Right-click in the folder and select "New" → "Text Document"
5. Name it: `claude_desktop_config.json` (make sure it ends with .json, not .txt!)
6. Right-click the file and select "Edit with Notepad"
7. Paste this (and replace the path with YOUR path):

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

8. **IMPORTANT:** 
   - Replace `C:\\Users\\YourName\\Documents\\yahoo-finance-mcp\\yahoo_finance_mcp.py` with YOUR actual path
   - Use double backslashes `\\` or forward slashes `/`
9. Save the file (Ctrl + S)
10. Close Notepad

### Step 4.3: How to Find Your Exact Path

**On Mac:**
1. Open Terminal
2. Type: `cd ` (with space)
3. Drag your yahoo-finance-mcp folder into Terminal
4. Press Enter
5. Type: `pwd`
6. This shows your path! Copy it.
7. Add `/yahoo_finance_mcp.py` to the end

**On Windows:**
1. Open File Explorer
2. Navigate to your yahoo-finance-mcp folder
3. Click in the address bar at the top
4. Copy the path (e.g., `C:\Users\YourName\Documents\yahoo-finance-mcp`)
5. Add `\yahoo_finance_mcp.py` to the end
6. Replace single `\` with double `\\` in the config file

---

## Part 5: Restart Claude Desktop

1. Close Claude Desktop completely
   - **Mac:** Press Cmd + Q or right-click the dock icon and select "Quit"
   - **Windows:** Right-click the system tray icon and select "Exit"

2. Wait a few seconds

3. Open Claude Desktop again

4. You should see the Yahoo Finance tools are now available!

---

## Part 6: Test It!

Try asking Claude these questions:

1. "What's the current price of Apple stock?"
2. "Show me Tesla's performance over the last year"
3. "Compare Apple, Microsoft, and Google"

If Claude responds with stock data, **congratulations!** 🎉 Everything is working!

---

## 🐛 Troubleshooting Common Issues

### Issue 1: "Command not found" or "Python not found"

**Solution:**
- Make sure Python is installed
- Try using `python3` instead of `python` in the config (Mac/Linux)
- Make sure you checked "Add to PATH" during Python installation (Windows)

### Issue 2: "Module not found: yfinance"

**Solution:**
- Run the installation script again
- Or manually run: `pip install yfinance pandas mcp`

### Issue 3: Tools not showing up in Claude

**Solution:**
1. Check your config file has the correct path
2. Make sure the JSON syntax is correct (no missing commas or brackets)
3. Restart Claude Desktop COMPLETELY (not just refresh)
4. Check that yahoo_finance_mcp.py actually exists at that path

### Issue 4: "No such file or directory"

**Solution:**
- Your path in the config file is wrong
- On Windows: Use `\\` instead of `\` (or use `/`)
- Make sure you used the FULL path (not just the folder name)
- Double-check the file actually exists at that location

### Issue 5: JSON Syntax Error

**Solution:**
Your config file might have a typo. It should look EXACTLY like this:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python3",
      "args": ["/full/path/to/yahoo_finance_mcp.py"]
    }
  }
}
```

Common mistakes:
- Missing commas
- Missing quotes
- Missing brackets or braces
- Wrong path format

---

## 📝 Config File Checklist

Before saving your config file, verify:

- [ ] Opening brace `{` at the start
- [ ] Closing brace `}` at the end
- [ ] `"mcpServers"` has quotes and a colon
- [ ] `"yahoo-finance"` has quotes and a colon
- [ ] `"command"` has quotes, colon, and value in quotes
- [ ] `"args"` has quotes, colon, and square brackets
- [ ] Path is in quotes and uses proper slashes
- [ ] All commas are in the right places
- [ ] No extra commas after the last item in any section

---

## ✅ Success Checklist

You've successfully set up the server if:

- [ ] Python is installed and working
- [ ] All required libraries are installed (yfinance, pandas, mcp)
- [ ] The yahoo_finance_mcp.py file is saved on your computer
- [ ] The claude_desktop_config.json file exists and has the correct path
- [ ] Claude Desktop has been restarted
- [ ] Claude can answer questions about stocks using the tools

---

## 🎉 You're Done!

You now have a fully functional Yahoo Finance MCP server! You can:

- Ask about any stock price
- View historical data
- Compare companies
- See financial statements
- Check analyst recommendations
- And much more!

Check out QUICK_REFERENCE.md for lots of example questions to ask.

---

## 🆘 Still Need Help?

If you've tried everything and it's still not working:

1. Make sure you followed EVERY step carefully
2. Check the troubleshooting section again
3. Double-check your config file syntax
4. Verify Python and all libraries are installed
5. Make sure the path in your config file is EXACTLY correct

The most common issue is an incorrect path in the config file. Take your time to get that right!

---

## 🎓 Next Steps

Once everything is working:

1. Read QUICK_REFERENCE.md for example queries
2. Try different types of questions
3. Explore different stocks and companies
4. Learn about financial metrics
5. Have fun analyzing the markets!

Remember: This tool provides data, not financial advice. Always do thorough research before making investment decisions! 📊✨
