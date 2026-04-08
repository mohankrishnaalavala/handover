/**
 * background.js — MV3 service worker
 *
 * Handles two actions from popup.js:
 *
 *   {action: "export", tabId}
 *     → Asks content script to fetch conversation via claude.ai API
 *     → Triggers chrome.downloads to save as handover-chat-<uuid>.json
 *     → Returns { success, filename } or { success: false, error }
 *
 *   {action: "handover", tabId}
 *     → Asks content script to extract conversation (API → DOM fallback)
 *     → POSTs to local handover server at /handover
 *     → Returns { success, result } or { success: false, error }
 */

"use strict";

const HANDOVER_PORT_KEY = "handover_port";
const HANDOVER_OUTPUT_KEY = "handover_output_dir";
const DEFAULT_PORT = 7437;

// ─── config helpers ───────────────────────────────────────────────────────────

async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get([HANDOVER_PORT_KEY, HANDOVER_OUTPUT_KEY], (items) => {
      resolve({
        port: items[HANDOVER_PORT_KEY] || DEFAULT_PORT,
        outputDir: items[HANDOVER_OUTPUT_KEY] || "",
      });
    });
  });
}

// ─── content script bridge ────────────────────────────────────────────────────

/**
 * Send a message to the tab's content script and return the response.
 */
function sendToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        const rawMsg = chrome.runtime.lastError.message || "";
        const msg = rawMsg.includes("Receiving end does not exist")
          ? "Content script not found — please refresh the tab and try again."
          : rawMsg || "Could not contact content script. Refresh the page and try again.";
        reject(new Error(msg));
        return;
      }
      if (!response || !response.success) {
        reject(new Error(response?.error || "Content script returned no data."));
        return;
      }
      resolve(response.data);
    });
  });
}

// ─── export action ────────────────────────────────────────────────────────────

/**
 * Fetch the full conversation via the claude.ai API and download as JSON.
 */
async function handleExport(tabId) {
  const conv = await sendToTab(tabId, { action: "export" });

  // conv = { uuid, name, chat_messages: [...] }
  const filename = `handover-chat-${conv.uuid || "export"}.json`;
  // Wrap in array so ClaudeParser can consume the file directly via CLI:
  // handover --input handover-chat-<uuid>.json --output ./my-project/
  const json = JSON.stringify([conv], null, 2);
  // Use a data: URL — Blob/URL.createObjectURL is not available in MV3 service workers
  const dataUrl =
    "data:application/json;charset=utf-8," + encodeURIComponent(json);

  return new Promise((resolve, reject) => {
    chrome.downloads.download({ url: dataUrl, filename, saveAs: false }, (downloadId) => {
      if (chrome.runtime.lastError || downloadId === undefined) {
        reject(new Error(chrome.runtime.lastError?.message || "Download failed."));
        return;
      }
      resolve({
        filename,
        messageCount: conv.chat_messages?.length ?? 0,
        title: conv.name,
      });
    });
  });
}

// ─── handover (live pipeline) action ─────────────────────────────────────────

async function postToServer(port, outputDir, payload) {
  if (outputDir) {
    try {
      await fetch(`http://localhost:${port}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: outputDir }),
      });
    } catch (_) {
      // Non-fatal
    }
  }

  const resp = await fetch(`http://localhost:${port}/handover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await resp.json();
  if (!resp.ok) throw new Error(data.message || `Server error ${resp.status}`);
  return data;
}

async function handleHandover(tabId, port, outputDir) {
  const payload = await sendToTab(tabId, { action: "extract" });
  return postToServer(port, outputDir, payload);
}

// ─── save-chat action ─────────────────────────────────────────────────────────

/**
 * Extract the conversation and POST it to /save-chat on the local server.
 * The server saves handover-chat-<uuid>.json to output_dir so the user can
 * run any CLI target against it:
 *   handover --input handover-chat-<uuid>.json --output <dir> --target copilot
 */
async function handleSave(tabId, port, outputDir) {
  if (outputDir) {
    try {
      await fetch(`http://localhost:${port}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: outputDir }),
      });
    } catch (_) {
      // Non-fatal
    }
  }

  const payload = await sendToTab(tabId, { action: "extract" });

  const resp = await fetch(`http://localhost:${port}/save-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const result = await resp.json();
  if (!resp.ok) throw new Error(result.message || `Server error ${resp.status}`);
  return result;
}

// ─── message listener ─────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  const { action, tabId } = request;

  if (action === "export") {
    handleExport(tabId)
      .then((result) => sendResponse({ success: true, result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (action === "handover") {
    // Fetch config first so the configured port is in scope for the error message
    getConfig().then(({ port, outputDir }) => {
      handleHandover(tabId, port, outputDir)
        .then((result) => sendResponse({ success: true, result }))
        .catch((err) => {
          const message = err instanceof Error ? err.message : String(err);
          const isServerDown =
            message.includes("Failed to fetch") ||
            message.includes("NetworkError") ||
            message.includes("ECONNREFUSED");
          sendResponse({
            success: false,
            error: isServerDown
              ? `Cannot reach handover server on port ${port}. Run: handover serve`
              : message,
          });
        });
    });
    return true;
  }

  if (action === "save") {
    getConfig().then(({ port, outputDir }) => {
      handleSave(tabId, port, outputDir)
        .then((result) => sendResponse({ success: true, result }))
        .catch((err) => {
          const message = err instanceof Error ? err.message : String(err);
          const isServerDown =
            message.includes("Failed to fetch") ||
            message.includes("NetworkError") ||
            message.includes("ECONNREFUSED");
          sendResponse({
            success: false,
            error: isServerDown
              ? `Cannot reach handover server on port ${port}. Run: handover serve`
              : message,
          });
        });
    });
    return true;
  }

  return false;
});
