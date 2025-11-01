#!/bin/bash

# Yahoo Finance MCP Server - Easy Installation Script
# This script will install all necessary dependencies

echo "🚀 Yahoo Finance MCP Server Installation"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null
then
    echo "❌ pip3 is not installed!"
    echo "Please install pip3"
    exit 1
fi

echo "✅ pip3 found"
echo ""

# Install dependencies
echo "📦 Installing required packages..."
echo ""

pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Add this server to your Claude Desktop config file"
    echo "2. Restart Claude Desktop"
    echo "3. Start asking about stocks!"
    echo ""
    echo "See README.md for detailed configuration instructions."
else
    echo ""
    echo "❌ Installation failed!"
    echo "Please check the error messages above and try again."
    exit 1
fi
