# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
