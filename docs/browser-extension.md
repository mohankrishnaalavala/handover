# Browser Extension — Install & Usage Guide

The **handover** browser extension lets you send any AI chat conversation to your local agent pipeline with one click. No manual export, no copy-paste.

**Supported browsers:** Chrome 116+, Firefox 109+ (both support Manifest V3)  
**Supported chat sites:** claude.ai, chatgpt.com (chat.openai.com)

---

## Support matrix

| Feature | claude.ai | chatgpt.com |
|---------|-----------|-------------|
| **Export Chat as JSON** (download for offline use) | ✅ Uses claude.ai API | ❌ Not supported — use CLI import instead |
| **Generate handover artifacts** (live pipeline via `handover serve`) | ✅ | ✅ |

> Gemini and Perplexity export parsing is supported by the **CLI** (`handover --input export.json`), but live browser extraction for those sites is not yet implemented in the extension.

---

## How it works

```
Browser tab (claude.ai / chatgpt.com)
      │  click "Generate handover artifacts"
      ▼
Extension popup  →  content script extracts conversation
      │
      ▼
background.js  ──POST /handover──▶  handover serve (localhost:<port>)
                                          │
                                     full pipeline:
                                     parse → summarize → generate
                                          │
                                    CLAUDE.md + PLAN.md (and more)
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

# Custom port
handover serve --port 8123

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

### Generate handover artifacts (claude.ai and chatgpt.com)

1. Navigate to a conversation on **claude.ai** or **chatgpt.com**
2. Click the **handover** toolbar icon
3. Set the **Output directory** to your project root (saved automatically)
4. Click **Generate handover artifacts**

The popup shows:
- `Extracting conversation…` — reading the page
- `Running handover pipeline…` — calling `handover serve`
- `Done — artifacts written to <path>` on success
- An error message if the server is not running or extraction failed

### Export Chat as JSON (claude.ai only)

1. Navigate to a conversation on **claude.ai**
2. Click the **handover** toolbar icon
3. Click **Export Chat as JSON**

The file downloads as `handover-chat-<uuid>.json`. Then run locally:

```bash
handover --input ~/Downloads/handover-chat-<uuid>.json --output ./my-project/ --no-llm
```

This is the recommended workflow for ChatGPT too — export from the ChatGPT web UI (Settings → Data Controls → Export Data), then pass the file to the CLI.

---

## Configuration

| Setting | Where | Default |
|---------|-------|---------|
| Output directory | Popup input field | `handover serve --output` value |
| Server port | Popup input field | `7437` |
| No-LLM mode | `handover serve --no-llm` | off |

Settings are saved in `chrome.storage.local` per browser profile.  
The port in the popup must match the port `handover serve` is listening on.

You can also update the server configuration at runtime:

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
{ "status": "ok", "version": "1.0.1" }
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

**"Cannot reach handover server on port \<port\>"**  
→ The server is not running on that port. Run `handover serve` (or `handover serve --port <port>` if you configured a custom port) in a terminal first.

**"No conversation found"**  
→ Make sure you are on a conversation page (not the home page). On ChatGPT, the URL should contain `/c/`. Scroll through the conversation once to ensure all messages are loaded.

**"Export as JSON requires a claude.ai conversation"**  
→ The Export button uses the claude.ai API and only works on claude.ai. For ChatGPT, use the ChatGPT web export or "Generate handover artifacts" instead.

**"Unsupported page"**  
→ The extension currently supports **claude.ai** and **chatgpt.com** (chat.openai.com). Gemini and Perplexity live extraction are not yet implemented — use the CLI with their exported files instead.

**Content script not responding after a navigation**  
→ Refresh the page and try again — MV3 service workers unload between navigations.

---

## Firefox compatibility

The same codebase targets Firefox 109+ (full MV3 support). Load it via  
`about:debugging → This Firefox → Load Temporary Add-on`.

For Firefox Add-on distribution, submit `dist/handover-extension.zip` to  
`addons.mozilla.org`.
