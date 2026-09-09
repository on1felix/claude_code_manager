# Claude Code Manager

Desktop control panel for [Claude Code](https://github.com/anthropics/claude-code) on Windows. Switches models and API endpoints, manages keys, installs and repairs the CLI — without touching the terminal or editing JSON by hand.

**Download:** [ClaudeCodeManager.exe (latest release)](https://github.com/on1felix/claude_code_manager/releases/latest/download/ClaudeCodeManager.exe)
No installation. Windows 10/11, 64-bit.

Docs, screenshots and updates: [claude-code-manager.netlify.app](https://claude-code-manager.netlify.app)

## Modes

Four provider modes, switched with one toggle — the app rewrites the Claude Code config for you:

- **Anthropic (FreeModel)** — route through a FreeModel-compatible proxy endpoint.
- **Official** — direct Anthropic API.
- **OpenAI** — OpenAI-compatible endpoint with model + effort pickers.
- **Custom URL** — any compatible base URL you enter.

## Features

- **Model picker** — visual model selection per mode, including reasoning-effort levels where supported.
- **1M context toggle** — switch Claude between the standard 200K and 1M-token context.
- **API key vaults** — store and switch keys for FreeModel, OpenAI and opencode endpoints. Each key card shows live usage bars, limit type and duration, balance reset time, and OTP support.
- **Base URL manager** — save, switch and manage custom endpoints (Omniroute, FreeModel and compatibles) per mode.
- **opencode integration** — provider presets, model catalog fetch (including free models) with reasoning flags, one-click provider config writing.
- **Claude Code install / update / uninstall** — installs via npm or winget, detects the installed version, compares with the latest GitHub release, blocks known-broken versions.
- **Codex CLI and opencode CLI** — same one-click install / version check / uninstall for both CLIs.
- **Node.js handling** — detects missing Node.js on start and installs it via winget automatically.
- **PATH fix** — adds the Claude binary directory to user PATH when the shell can't find it.
- **Status line** — preview, install and uninstall the Claude Code status line with one button.
- **Fix Claude** — repairs a broken `~/.claude.json` (backups included), fixes the `installMethod` "missing or broken" error, pins `DISABLE_UPDATES` so Claude doesn't self-update into an incompatible version.
- **Launch buttons** — start Claude, Codex or opencode straight from the app with the active config applied.
- **Online usage polling** — live key usage pulled from the provider API in the background.
- **Self-update** — checks its own releases on start and updates in one click.
- **RU / EN interface** — full bilingual UI.

## Use cases

- **First setup** — installs Node.js, Claude Code and the status line, then gets you on a working endpoint in minutes.
- **Key rotation** — keep several API keys with limits and switch the active one without editing files.
- **Broken CLI** — Fix Claude repairs configs that `claude` itself refuses to start with.

## Run from source

```bash
pip install PySide6
python claude_code_manager.pyw
```

Build the exe: `build.bat` (needs PyInstaller — `pip install pyinstaller`).

## Notes

- Requires Node.js (the app installs it for you if missing) and a Claude subscription or API access depending on the mode.
- Unsigned `.exe` may trigger antivirus heuristics — false positive. The source is open; build it yourself to verify.

---

By [on1felix](https://github.com/on1felix). Open source, free, no ads.
Questions: Telegram [@On1Felix](https://t.me/On1Felix).
