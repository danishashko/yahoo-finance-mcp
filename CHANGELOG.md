# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.1.0]: https://github.com/danishashko/yahoo-finance-mcp/releases/tag/v1.1.0
[1.0.0]: https://github.com/danishashko/yahoo-finance-mcp/releases/tag/v1.0.0
