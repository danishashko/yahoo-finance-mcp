# Containerized MCP server for Glama release builds.
# The server speaks the Model Context Protocol over stdio.
FROM python:3.12-slim

# No .pyc files; unbuffered stdout/stderr so the JSON-RPC stream stays clean.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server.
COPY yahoo_finance_mcp.py ./

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# MCP communicates over stdio.
CMD ["python", "yahoo_finance_mcp.py"]
