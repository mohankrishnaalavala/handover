# Browser Extension — Install & Usage Guide

The **handover** browser extension lets you send any AI chat conversation to your local Claude Code agent with one click. No manual export, no copy-paste.

**Supported browsers:** Chrome 116+, Firefox 109+ (both support Manifest V3)  
**Supported chat sites:** claude.ai, chat.openai.com

---

## How it works

```
Browser tab (claude.ai / chat.openai.com)
      │  click "Send to Claude Code"
      ▼
Extension popup  →  content script extracts DOM messages
      │
      ▼
background.js  ──POST /handover──▶  handover serve (localhost:7437)
                                          │
                                     full pipeline:
                                     parse → summarize → generate
                                          │
                                    CLAUDE.md + PLAN.md
                                     written to output dir
```

---

## Prerequisites

1. **handover** installed: `pip install handover`
2. **ANTHROPIC_API_KEY** set in your shell (or use `--no-llm` for offline mode)
3. The local bridge server running: `handover serve`

---

## Start the server

```bash
# Default — writes artifacts to the current directory
handover serve

# Specify an output project directory
handover serve --output ~/projects/myapp/

# Offline mode (no API key required)
handover serve --no-llm

# Run in the background (logs → ~/.handover/server.log)
handover serve --output ~/projects/myapp/ --daemon
```

The server listens on `http://localhost:7437` by default.  
Port 7437 spells **H-A-N-D** on a phone keypad.

---

## Install the extension

### Chrome / Chromium

1. Clone the repo or download the source
2. In Chrome, go to `chrome://extensions`
3. Enable **Developer mode** (top-right toggle)
4. Click **Load unpacked**
5. Select the `extension/` directory from the repo

### Firefox

1. Open `about:debugging`
2. Click **This Firefox** → **Load Temporary Add-on**
3. Select `extension/manifest.json`

### Build a distributable zip

```bash
bash scripts/build-extension.sh
# Output: dist/handover-extension.zip
```

---

## Usage

1. Navigate to a conversation on **claude.ai** or **chat.openai.com**
2. Click the **handover** toolbar icon
3. Set the **Output directory** to your project root (saved automatically)
4. Click **Send to Claude Code**

The popup shows:
- `Extracting conversation…` — reading the DOM
- `Running handover pipeline…` — calling `handover serve`
- `Done — CLAUDE.md written to <path>` on success
- An error message if the server is not running or extraction failed

---

## Configuration

| Setting | Where | Default |
|---------|-------|---------|
| Output directory | Popup input field | `handover serve --output` value |
| Server port | Popup input field | `7437` |
| No-LLM mode | `handover serve --no-llm` | off |

Settings are saved in `chrome.storage.local` per browser profile.

You can also update the server configuration at runtime via the API:

```bash
curl -X POST http://localhost:7437/config \
  -H "Content-Type: application/json" \
  -d '{"output_dir": "/path/to/project", "no_llm": false}'
```

---

## API reference

The local server exposes three endpoints:

### `GET /health`

Returns server status and version.

```json
{ "status": "ok", "version": "0.3.0" }
```

### `POST /handover`

Run the full handover pipeline.

**Request body:**
```json
{
  "source": "claude",
  "conversation": { /* raw conversation JSON from the page */ }
}
```

**Response:**
```json
{
  "status": "ok",
  "claude_md": "/path/to/CLAUDE.md",
  "plan_md": "/path/to/PLAN.md"
}
```

Valid `source` values: `claude`, `chatgpt`, `gemini`, `perplexity`

### `POST /config`

Update the server configuration without restarting.

```json
{ "output_dir": "/new/path", "no_llm": true }
```

---

## Troubleshooting

**"Cannot reach handover server on port 7437"**  
→ The server is not running. Run `handover serve` in a terminal first.

**"No conversation found"**  
→ Make sure you are on a conversation page (not the Claude home page or ChatGPT home). Scroll through the conversation once to ensure all messages are loaded in the DOM.

**"Unsupported page"**  
→ The extension only works on `claude.ai` and `chat.openai.com` (Gemini and Perplexity DOM scrapers are planned for v0.3.1).

**Content script not responding after a navigation**  
→ Refresh the page and try again — MV3 service workers unload between navigations.

---

## Firefox compatibility

The same codebase targets Firefox 109+ (full MV3 support). Load it via  
`about:debugging → This Firefox → Load Temporary Add-on`.

For Firefox Add-on distribution, submit `dist/handover-extension.zip` to  
`addons.mozilla.org`.
