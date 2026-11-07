# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.1] - 2026-11-07

### Fixed

- `get_market_status` described regions (CA, DE, FR, IN, JP, HK, AU) that it
  does not accept. The description now lists the real values: US, GB, ASIA,
  EUROPE, RATES, COMMODITIES, CURRENCIES and CRYPTOCURRENCIES.
- README: the package and repo line showed a literal `&nbsp;` on sites that
  do not render HTML entities.

### Changed

- Clearer tool descriptions for `screen_stocks`, `get_holders`,
  `search_symbols`, `get_earnings` and `get_analyst_recommendations`: when not
  to use each tool and which tool to use instead, how fresh the data is, and
  how `count` and `limit` behave. No change to inputs or outputs.

## [1.6.0] - 2026-11-06

### Added

- Structured output. Every tool publishes an `outputSchema`, and every result
  carries its data as `structuredContent` next to the text, whichever
  `response_format` was asked for. Clients that read structured content get
  typed fields; others read the text as before. Checked on 36 live calls
  across all 18 tools: every result validates against its schema, and the
  Markdown text is unchanged apart from the options chain below.

### Changed

- JSON says missing with `null` instead of the string "N/A".
- `get_options_chain` returns the strikes nearest the current price, with the
  underlying price. It used to return the first 40 rows, the deep
  in-the-money strikes, and a full chain in JSON was over the size limit.
- `get_market_status` takes the markets yfinance accepts: US, GB, ASIA,
  EUROPE, RATES, COMMODITIES, CURRENCIES, CRYPTOCURRENCIES. The codes it
  listed before (JP, DE, CA and others) all failed.

### Fixed

- A JSON payload over the size limit came back as a successful
  `{"error": "response_too_large"}` object. It is now an error result, and the
  two tools that hit it keep the useful rows instead: `get_holders` with
  `insider_transactions` returns the newest trades that fit (newest first),
  and `get_options_chain` the strikes nearest the money.
- `get_earnings` ignored `limit`: yfinance returns at least 25 dates whatever
  it is asked for, so the history and the beat count always covered 25.

## [1.5.1] - 2026-11-06

### Fixed

- The first burst of parallel calls after startup took about 8 seconds for 8
  quotes. The cause is curl_cffi 0.17 (required by yfinance 1.8): its `chrome`
  and `firefox` impersonation profiles stall the first request on every new
  thread, against any host. The shared session now impersonates Safari, which
  does not. Measured over HTTP, 8 parallel quotes: 1.26s on the first burst
  (was 7.7s), 1.06s on the next, 0.93s after 20 seconds idle.

## [1.5.0] - 2026-11-06

### Changed

- Moved to the MCP Python SDK v2 (`mcp>=2.3,<3`). `FastMCP` is now
  `MCPServer`; the SDK runs each tool on a worker thread itself, so the
  `@offload` wrapper is gone. Clients see no change in tool names or arguments.
- Failures are now real MCP errors (`isError: true`) instead of ordinary text
  an agent had to read to recognise: unknown symbols, an expiration date that
  does not exist, an end date before the start date, an unknown industry key,
  Yahoo rate-limiting, and upstream failures.
- Tools no longer advertise an output schema that only wrapped the text in
  `{"result": ...}`.

### Fixed

- An unknown ticker returned a full page of N/A fields as a successful call.
  `get_stock_quote`, `get_company_info`, `get_analyst_recommendations` and
  `compare_stocks` now answer "Unknown symbol", pointing to `search_symbols`.
- `BRK.B` and `BRK/B` returned an empty quote: Yahoo spells class shares
  `BRK-B`. They are rewritten; exchange suffixes such as `BP.L` and `7203.T`
  pass through unchanged.
- Prices in other currencies were printed with `$`. Quotes, company info and
  analyst targets now use the listing's currency (`3,338.00 JPY`), and the
  quote states its exchange, currency, market state and timestamp, in Markdown
  and JSON. `compare_stocks` adds a currency column and no longer names a
  "highest price" across different currencies.
- `get_market_news` put stories about other companies first (an MP Materials
  call for AAPL). Stories led by the ticker now come first, and each item
  lists the tickers it is tagged with and whether it is primarily about the
  requested one.

### Known issue

- The first burst of parallel calls after startup is slow on curl_cffi 0.17.
  Fixed in 1.5.1.

## [1.4.0] - 2026-11-06

### Added

- `get_earnings`: the next earnings date with days until it, consensus EPS and
  revenue ranges, the next ex-dividend date, and the beat/miss history with
  surprise %.
- `get_earnings_calendar`: every company reporting in a date range, largest
  first, with BMO/AMC timing, EPS estimate and, once reported, the surprise.
- `screen_stocks`: Yahoo's 19 predefined screeners (day gainers and losers,
  most active, most shorted, undervalued growth and large caps, top ETFs and
  funds) with relative volume, P/E and 52-week range.
- `get_fund_data`: ETF and mutual fund holdings, expense ratio and turnover
  against the category average, sector weights and asset classes.
- `get_sector_overview`: a sector or one of its industries, with its largest
  companies, its industries, top growth companies and top performers.
- `get_holders` gains `insider_purchases` (6-month net insider buying) and
  `insider_roster` (each insider and their stake).
- Server instructions: a client now receives a short map of which tool answers
  what on connect.
- `llms.txt` and `AGENTS.md` for agents using or working on the server.
- `serverInfo.version` now reports this server's version. It reported the MCP
  SDK's version (1.27.2) instead.

### Changed

- yfinance minimum raised to 1.8, the version these tools were tested on. The
  earnings calendar does not exist before 1.0.

## [1.3.1] - 2026-09-08

### Fixed

- Non-finite numbers no longer make a successful response unparseable. Python
  writes `NaN`, `Infinity` and `-Infinity` bare and none of the three is valid
  JSON, so any figure yfinance did not supply took the whole document down at
  the client's `JSON.parse` - `get_analyst_estimates` hit this on the LTG
  growth row for most tickers, including AAPL. Every non-finite float now
  serialises as `null`, which says exactly what was true: the value was
  missing. The failure was silent, so the symptom was a green call whose
  downstream fields all arrived empty.
- Blocking tool bodies no longer stall the event loop. Every tool here is
  blocking I/O declared `async def` with no await in it, and the MCP SDK calls
  an async tool straight on the loop - invisible over stdio, where one request
  is in flight at a time, and serious over HTTP, where one slow call stalls
  every other client. Tool bodies now run through `anyio.to_thread`. Measured
  2026-09-08: eight concurrent ticker requests went from all finishing together
  at 10.3 seconds to all finishing at 1.2.

## [1.3.0] - 2026-09-04

### Added

- `--http` serves the same 13 tools over Streamable HTTP at `/mcp`, alongside
  `--host`, `--port`, `--allowed-host` and `--stateful`. stdio is still the
  default and is unchanged. This exists because a client that only accepts a
  URL - n8n's MCP Client Tool node offers HTTP Streamable and SSE and no way to
  spawn a command - could not reach a stdio-only server at all.
- DNS-rebinding protection now follows the host actually bound. FastMCP decides
  its allow-list inside the constructor from the host it was given, so binding
  wider at run time previously left the built-in localhost list rejecting the
  very clients the wider bind was for, with a bare `421 Misdirected Request`.
  `localhost`, `127.0.0.1` and `host.docker.internal` on the bound port are
  accepted by default; anything else needs `--allowed-host`.

### Fixed

- **`get_financial_statements` returned an error in JSON mode for every
  ticker.** The statement frames are keyed by pandas Timestamp columns, and
  `json.dumps` coerces values through `default=` but never keys, so the tool
  answered `keys must be str, int, float, bool or None, not Timestamp`. Markdown
  was unaffected, which is why it went unnoticed.
- **`get_analyst_recommendations` returned nothing in JSON mode for every
  widely covered stock.** The markdown branch caps the upgrades/downgrades frame
  at ten rows; the JSON branch serialised the entire rating history, reaching
  ~263,000 characters on NVDA. Over the response limit, JSON is refused outright
  rather than truncated, so the price targets and consensus were lost too.
  Measured before the fix on NVDA, AAPL, MSFT, PLTR and F: all five refused.
- **`get_historical_prices` refused a year of daily bars in JSON mode** for the
  same reason. It now returns as many of the newest records as fit, with
  `totalRecords`, `returnedRecords` and `truncated` so the caller can see what
  was left out.
- Three statements at once exceeded the response limit, so JSON now applies the
  same per-statement 30-row cap the markdown branch already used, and reports
  the true line-item count in `lineItemCounts`.
- The markdown truncation note read the row count after the frame had already
  been replaced by its own head, so it always claimed the cap as the total
  ("Showing first 30 rows of 30 total").

## [1.2.5] - 2026-08-06

### Added

- Troubleshooting entry for running behind a non-Anthropic model or proxy
  (LiteLLM, OpenRouter, NVIDIA NIM, local models). The server never talks to a
  model, so the usual causes are a model without function calling, or a proxy
  dropping unsupported parameters and silently stripping tool definitions.

### Changed

- README section order now matches the other servers in this family:
  Troubleshooting comes before Manual Installation.

## [1.2.4] - 2026-07-30

### Fixed

- Fresh installs no longer crash on startup. `requirements.txt` had no upper
  bound on `mcp`, so after the MCP Python SDK 2.0.0 release (2026-07-28)
  `pip install -r requirements.txt` pulled 2.x, which removed
  `mcp.server.fastmcp` and made the server die with
  `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. The requirement
  is now `mcp>=1.2.0,<2`. Existing installs were unaffected (the launcher
  caches its virtualenv per requirements hash).

## [1.2.3] - 2026-06-06

### Changed

- Enriched every tool description with purpose, when-to-use/disambiguation
  guidance, and return/error behavior. This raises self-describing quality for
  AI agents (and Glama's Tool Definition Quality score) while staying lean
  (~140 tokens per tool); parameters remain self-documented via their field
  descriptions.

### Added

- `Dockerfile`, `.dockerignore`, and `glama.json` to support a containerized
  Glama release (builds `python:3.12-slim`, runs the server over stdio as a
  non-root user). Verified locally: the image builds and `tools/list` returns
  all 13 tools.

## [1.2.2] - 2026-06-04

### Fixed

- Oversized responses no longer overflow the response size cap. Previously a
  too-large JSON response could be returned larger than the limit (and dumped a
  giant truncated preview into context); it now returns a small message asking
  to narrow the request.

### Changed

- Trimmed verbose tool descriptions to cut the always-loaded schema size
  (~1,800 fewer tokens on connect). Tool behavior unchanged.

## [1.2.1] - 2026-06-02

Packaging only. No runtime code changes.

### Added

- `server.json` and an `mcpName` field for listing on the official MCP Registry.

## [1.2.0] - 2026-06-01

Major feature release: **seven new data tools (6 → 13)** plus rate-limit
hardening. Every tool was verified end to end by driving the real MCP server
over stdio against live Yahoo Finance data.

### Added

- **`get_market_news`** — latest news headlines for a ticker, with source,
  date, summary, and link. Handles the modern nested yfinance news format.
- **`get_options_chain`** — list available expiration dates, or fetch the
  calls/puts chain (strike, bid/ask, volume, open interest, implied
  volatility) for a given expiration.
- **`get_holders`** — institutional holders, mutual-fund holders, the
  major-holders breakdown, or recent insider transactions.
- **`get_dividends_splits`** — full dividend payment history (with a trailing
  summary) and stock-split history.
- **`get_analyst_estimates`** — forward analyst price targets, EPS and revenue
  estimates by period, and growth estimates (complements the existing
  recommendations tool).
- **`search_symbols`** — find ticker symbols by company name or keyword, with
  exchange, type, sector, and industry.
- **`get_market_status`** — whether a market (by region) is open or closed,
  with timing and a summary of its major indices.
- **Shared `curl_cffi` browser-impersonating HTTP session** reused across all
  tools. This cuts down on Yahoo's HTTP 429 rate-limiting and speeds up
  repeated calls; it degrades gracefully to the default session if
  `curl_cffi` is unavailable.
- Friendly, specific handling of `YFRateLimitError` ("wait and retry")
  across all tools.

### Changed

- `requirements.txt`: add `curl_cffi`; raise the `yfinance` floor to
  `>=0.2.61` (which carries upstream rate-limit-handling fixes and the
  `Search`/`Market` APIs used by the new tools).

## [1.1.1] - 2026-05-31

Documentation and packaging only. No runtime code changes; behavior is
identical to 1.1.0.

### Changed

- Reworked the README: clearer structure, a tools table with parameters and
  supported `period`/`interval` values, example prompts, and a note clarifying
  that the repository name (`yahoo-finance-mcp`) differs from the npm package
  name (`yahoo-finance-mcp-server`).
- Added shields.io badges, including a monthly-downloads pill and a Python
  version badge.
- Normalized `repository.url` to the `git+https://` form npm expects.

### Added

- This `CHANGELOG.md`, now shipped in the npm tarball.

## [1.1.0] - 2026-05-30

A full QA pass that fixed several bugs which broke core functionality, and made
the documented `npx` installation actually work. Every fix was verified end to
end by driving the real MCP server over stdio against live Yahoo Finance data.

### Fixed

- **Tool inputs failed validation.** Each tool took a single Pydantic model
  argument, so the MCP schema nested every field under a required `params`
  object while the docs told the model to send fields directly. The result was
  that calls were rejected. Tools now expose their parameters directly.
- **`get_analyst_recommendations` crashed** with `'RangeIndex' object has no
  attribute 'strftime'` due to a change in the `yfinance` recommendations
  format. It now reads the current format and also reports recent
  upgrades/downgrades.
- **Dividend yield was shown 100x too high** (for example `35.00%` for AAPL).
  Modern `yfinance` already returns this value as a percentage, so it is no
  longer multiplied again.
- **Markdown tables broke** when the optional `tabulate` package was missing.
  It is now a declared dependency, with a graceful plain-text fallback.
- **Truncated JSON responses are now valid JSON** instead of being cut off
  mid-structure.

### Added

- **`bin/cli.js` Node launcher** so `npx -y yahoo-finance-mcp-server` works. It
  locates Python 3.10+, creates an isolated virtual environment, installs the
  Python dependencies on first run, and starts the server with the protocol
  stream kept clean on stdout.
- `tabulate` added to the dependencies.

### Changed

- `package.json` `bin` now points at the Node launcher, the binary name matches
  the package name, and a Node engine requirement was added.
- Tightened dependency floors (`yfinance>=0.2.40`, `mcp>=1.2.0`).
- Replaced the deprecated Pydantic `min_items`/`max_items` with
  `min_length`/`max_length`.
- Rewrote the README and corrected the installation and troubleshooting docs.

## [1.0.0] - 2025-11-01

### Added

- Initial release of the Yahoo Finance MCP Server, distributed on npm.
- Six tools: `get_stock_quote`, `get_historical_prices`, `get_company_info`,
  `get_financial_statements`, `compare_stocks`, and
  `get_analyst_recommendations`.
- Markdown and JSON output formats.

[1.2.0]: https://github.com/danishashko/yahoo-finance-mcp/releases/tag/v1.2.0
[1.1.1]: https://github.com/danishashko/yahoo-finance-mcp/releases/tag/v1.1.1
[1.1.0]: https://github.com/danishashko/yahoo-finance-mcp/releases/tag/v1.1.0
[1.0.0]: https://github.com/danishashko/yahoo-finance-mcp/releases/tag/v1.0.0
