#!/usr/bin/env node
"use strict";

/**
 * Cross-platform launcher for the Yahoo Finance MCP server.
 *
 * The server itself is written in Python (FastMCP + yfinance). This wrapper lets
 * the package be started with `npx -y yahoo-finance-mcp-server` (or a global
 * install) by:
 *   1. locating a suitable Python interpreter (>= 3.10),
 *   2. creating an isolated virtual environment on first run and installing the
 *      Python dependencies into it,
 *   3. spawning the server with stdio inherited so the MCP JSON-RPC stream
 *      passes straight through.
 *
 * IMPORTANT: stdout is the MCP protocol channel. This wrapper must never write
 * anything to stdout. All diagnostics go to stderr.
 */

const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");

const PKG_ROOT = path.resolve(__dirname, "..");
const SERVER = path.join(PKG_ROOT, "yahoo_finance_mcp.py");
const REQUIREMENTS = path.join(PKG_ROOT, "requirements.txt");

function log(msg) {
  process.stderr.write(`[yahoo-finance-mcp] ${msg}\n`);
}

function die(msg, code = 1) {
  log(msg);
  process.exit(code);
}

function probePython(cmd) {
  try {
    const r = spawnSync(
      cmd,
      ["-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
      { encoding: "utf8" }
    );
    if (r.status === 0 && r.stdout) {
      const [maj, min] = r.stdout.trim().split(".").map(Number);
      if (maj > 3 || (maj === 3 && min >= 10)) {
        return { cmd, version: r.stdout.trim() };
      }
    }
  } catch (_) {
    /* not found / not runnable */
  }
  return null;
}

function findPython() {
  const candidates =
    process.platform === "win32"
      ? ["python", "py", "python3"]
      : ["python3", "python"];
  for (const c of candidates) {
    const found = probePython(c);
    if (found) return found;
  }
  return null;
}

function venvPythonPath(venvDir) {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function requirementsHash() {
  try {
    return crypto
      .createHash("sha256")
      .update(fs.readFileSync(REQUIREMENTS))
      .digest("hex")
      .slice(0, 16);
  } catch (_) {
    return "norequirements";
  }
}

function ensurePythonEnv() {
  const baseCache =
    process.env.YAHOO_FINANCE_MCP_HOME ||
    path.join(os.homedir() || os.tmpdir(), ".cache", "yahoo-finance-mcp");
  const venvDir = path.join(baseCache, "venv");
  const py = venvPythonPath(venvDir);
  const sentinel = path.join(venvDir, `.deps-${requirementsHash()}`);

  // Fast path: venv already exists and deps for this requirements set installed.
  if (fs.existsSync(py) && fs.existsSync(sentinel)) {
    return py;
  }

  const sys = findPython();
  if (!sys) {
    die(
      "Python 3.10+ is required but was not found.\n" +
        "Install it from https://www.python.org/downloads/ and make sure " +
        "`python3` (or `python`) is on your PATH."
    );
  }
  log(`Using ${sys.cmd} (Python ${sys.version}).`);

  fs.mkdirSync(baseCache, { recursive: true });

  if (!fs.existsSync(py)) {
    log("First run: creating an isolated Python environment (one-time setup)...");
    const v = spawnSync(sys.cmd, ["-m", "venv", venvDir], {
      stdio: ["ignore", 2, 2],
    });
    if (v.status !== 0) {
      die("Failed to create a Python virtual environment.");
    }
  }

  log("Installing Python dependencies (yfinance, pandas, mcp, ...) - this may take a minute...");
  const pipArgs = [
    "-m",
    "pip",
    "install",
    "--disable-pip-version-check",
    "-q",
    "-r",
    REQUIREMENTS,
  ];
  let pip = spawnSync(py, pipArgs, { stdio: ["ignore", 2, 2] });
  if (pip.status !== 0) {
    // Upgrade pip once and retry; older bundled pip sometimes fails on wheels.
    spawnSync(py, ["-m", "pip", "install", "--upgrade", "pip"], {
      stdio: ["ignore", 2, 2],
    });
    pip = spawnSync(py, pipArgs, { stdio: ["ignore", 2, 2] });
    if (pip.status !== 0) {
      die("Failed to install Python dependencies. See the errors above.");
    }
  }

  fs.writeFileSync(sentinel, new Date().toISOString());
  log("Setup complete.");
  return py;
}

function main() {
  if (!fs.existsSync(SERVER)) {
    die(`Server entry point not found: ${SERVER}`);
  }

  const python = ensurePythonEnv();

  const child = spawn(python, [SERVER, ...process.argv.slice(2)], {
    stdio: "inherit",
  });

  child.on("error", (err) => die(`Failed to start the server: ${err.message}`));

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
    } else {
      process.exit(code == null ? 0 : code);
    }
  });

  for (const sig of ["SIGINT", "SIGTERM"]) {
    process.on(sig, () => {
      try {
        child.kill(sig);
      } catch (_) {
        /* already gone */
      }
    });
  }
}

main();
