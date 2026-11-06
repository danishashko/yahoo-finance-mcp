# AGENTS.md

Rules for an agent changing this repo. For what the server does, read `llms.txt` and `README.md`.

## Layout

- `yahoo_finance_mcp.py` is the whole server: FastMCP on the `mcp` Python SDK, data from yfinance.
- `bin/cli.js` is the npx wrapper. It builds a venv and reinstalls dependencies whenever `requirements.txt` changes (it hashes the file).
- `server.json` is the MCP registry manifest. `package.json` is the npm package.

## Invariants

- Every tool is decorated `@mcp.tool(...)` then `@offload`. `@offload` runs the blocking body in a worker thread; without it one slow call stalls every HTTP client.
- Every tool carries `annotations` (`title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and a `response_format` parameter.
- JSON output goes through `_json()`, never `json.dumps` directly. yfinance returns NaN for missing figures and bare NaN is invalid JSON.
- Oversized output goes through `truncate_response` (markdown) or `truncate_json_response` / `_fit_records` (JSON). Never return more than `CHARACTER_LIMIT`.
- Errors go through `_error()`, which recognises Yahoo rate-limiting.
- Use `make_ticker()` and `_get_session()` so every call shares one browser-impersonating session.
- `mcp` stays pinned below 2: the v2 SDK removed `mcp.server.fastmcp`.

## Checks before a release

1. `ruff check yahoo_finance_mcp.py`
2. Call every tool in both `markdown` and `json` against live Yahoo data, including one symbol that has no data for that tool (an ETF for `get_earnings`, a stock for `get_fund_data`). Every JSON reply must parse.
3. If a tool was added, update the README tool table, `llms.txt`, the server `instructions` string, and the tool count in the README.

## Releasing

- Bump the version in `package.json`, both places in `server.json`, and `__version__` in `yahoo_finance_mcp.py`, and add a `CHANGELOG.md` entry.
- Commit, tag `v<x.y.z>`, push, `npm publish`, then `mcp-publisher publish server.json`, then create the GitHub release from the changelog entry.
- No AI co-author or attribution trailer on any commit.
