#!/usr/bin/env python3
"""
Yahoo Finance MCP Server - Installation Test Script

This script verifies that all required packages are installed correctly
and that the server can connect to Yahoo Finance.
"""

import sys

print("=" * 60)
print("Yahoo Finance MCP Server - Installation Test")
print("=" * 60)
print()

# Test 1: Python Version
print("Test 1: Checking Python version...")
version = sys.version_info
if version.major >= 3 and version.minor >= 8:
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
else:
    print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Need Python 3.8+")
    sys.exit(1)
print()

# Test 2: Required Packages
print("Test 2: Checking required packages...")
required_packages = {
    'yfinance': 'yfinance',
    'pandas': 'pandas',
    'pydantic': 'pydantic',
    'httpx': 'httpx',
    'mcp': 'mcp'
}

all_packages_ok = True
for package_name, import_name in required_packages.items():
    try:
        __import__(import_name)
        print(f"✅ {package_name} - Installed")
    except ImportError:
        print(f"❌ {package_name} - NOT installed")
        all_packages_ok = False

if not all_packages_ok:
    print()
    print("⚠️  Some packages are missing!")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)
print()

# Test 3: Yahoo Finance Connection
print("Test 3: Testing Yahoo Finance connection...")
try:
    import yfinance as yf
    ticker = yf.Ticker("AAPL")
    info = ticker.info
    price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
    
    if price != 'N/A':
        print(f"✅ Successfully fetched Apple stock price: ${price}")
    else:
        print("⚠️  Connected but couldn't get price (this is OK)")
except Exception as e:
    print(f"❌ Error connecting to Yahoo Finance: {str(e)}")
    print("Check your internet connection")
    all_packages_ok = False
print()

# Test 4: MCP Server File
print("Test 4: Checking MCP server file...")
import os
server_file = "yahoo_finance_mcp.py"
if os.path.exists(server_file):
    print(f"✅ {server_file} - Found")
    
    # Check if it's valid Python
    try:
        with open(server_file, 'r') as f:
            compile(f.read(), server_file, 'exec')
        print(f"✅ {server_file} - Valid Python syntax")
    except SyntaxError as e:
        print(f"❌ {server_file} - Syntax error: {e}")
        all_packages_ok = False
else:
    print(f"❌ {server_file} - Not found in current directory")
    all_packages_ok = False
print()

# Final Result
print("=" * 60)
if all_packages_ok:
    print("🎉 All tests passed! Your installation looks good!")
    print()
    print("Next steps:")
    print("1. Configure Claude Desktop (see SETUP_GUIDE.md)")
    print("2. Restart Claude Desktop")
    print("3. Try asking: 'What's the price of Apple stock?'")
else:
    print("⚠️  Some tests failed. Please fix the issues above.")
    print()
    print("Common solutions:")
    print("- Install missing packages: pip install -r requirements.txt")
    print("- Check your internet connection")
    print("- Make sure yahoo_finance_mcp.py is in this directory")
print("=" * 60)
