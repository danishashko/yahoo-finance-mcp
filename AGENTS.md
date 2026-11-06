# AGENTS.md

Rules for an agent changing this repo. For what the server does, read `llms.txt` and `README.md`.

## Layout

- `yahoo_finance_mcp.py` is the whole server: `MCPServer` from the `mcp` Python SDK v2, data from yfinance.
- `bin/cli.js` is the npx wrapper. It builds a venv and reinstalls dependencies whenever `requirements.txt` changes (it hashes the file).
- `server.json` is the MCP registry manifest. `package.json` is the npm package.

## Invariants

- Tools are plain sync `def`s decorated `@mcp.tool(structured_output=False, ...)` then `@structured(<Model>Out)`. SDK v2 runs a sync tool on a worker thread, so one slow call does not stall other HTTP clients. Never make a tool `async def` without awaiting real async I/O: an async tool runs on the event loop.
- Every tool carries `annotations` (`title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and a `response_format` parameter.
- Each tool builds its text in `_md()` and its JSON in `_js()` and returns `_respond(response_format, _md, _js)`. `_js()` always runs: its payload is the structured content, so it must match the tool's `<Model>Out` in the STRUCTURED OUTPUT section. A new field goes in both. `_publish_output_schemas()` publishes the schemas; they are not enforced at call time, so the release check enforces them.
- JSON output goes through `_json()`, never `json.dumps` directly. yfinance returns NaN for missing figures and bare NaN is invalid JSON; `_json()` also turns the Markdown placeholder "N/A" into null.
- Oversized output goes through `truncate_response` (markdown) or `truncate_json_response` / `_fit_records` (JSON). Never return more than `CHARACTER_LIMIT`. Prefer trimming to the useful rows (`_fit_records`, the options chain's nearest strikes) over `truncate_json_response`, which fails a JSON request.
- Failures raise `ToolError` (via `_error()`, which also recognises Yahoo rate-limiting), so the client gets `isError: true`. Never return an error as plain text. "No data for this symbol" is a normal answer, not an error.
- A tool that reads `.info` calls `_require_known()`: yfinance does not raise for an unknown symbol, it returns empty fields.
- `_norm_ticker()` rewrites class shares (BRK.B, BRK/B) to Yahoo's BRK-B. Every ticker argument goes through it.
- Use `make_ticker()` and `_get_session()` so every call shares one browser-impersonating session.
- The shared session impersonates `safari`, not `chrome`. On curl_cffi 0.17 (required by yfinance 1.8) the `chrome` and `firefox` profiles stall the first request on every new thread, against any host, so parallel bursts queued up for ~8s. `safari` and `edge` do not. Do not switch back without re-running the concurrency check.
- Concurrency check before a release: over `--http`, fire three bursts of 8 parallel `get_stock_quote` calls. Every burst, including the first and one after 20 seconds idle, should finish in about 1 second.

## Checks before a release

1. `ruff check yahoo_finance_mcp.py`
2. Call every tool in both `markdown` and `json` against live Yahoo data through an MCP client, including one symbol that has no data for that tool (an ETF for `get_earnings`, a stock for `get_fund_data`). Every JSON reply must parse, and every `structuredContent` must validate against the tool's `outputSchema` with a JSON Schema validator (`jsonschema`).
3. If a tool was added, update the README tool table, `llms.txt`, the server `instructions` string, and the tool count in the README.

## Releasing

- Bump the version in `package.json`, both places in `server.json`, and `__version__` in `yahoo_finance_mcp.py`, and add a `CHANGELOG.md` entry.
- Commit, tag `v<x.y.z>`, push, `npm publish`, then `mcp-publisher publish server.json`, then create the GitHub release from the changelog entry.
- No AI co-author or attribution trailer on any commit.
