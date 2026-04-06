/**
 * popup.js — handover Chrome extension popup
 *
 * Two buttons:
 *   btn-export   → "Export Chat as JSON"
 *                  Calls background {action:"export"} → downloads handover-chat-<uuid>.json
 *                  Shows: filename + CLI command to run locally
 *
 *   btn-handover → "Send to Claude Code" (requires handover serve)
 *                  Calls background {action:"handover"} → POSTs to local server
 *                  Shows: path of generated CLAUDE.md
 */

"use strict";

const STORAGE_PORT_KEY = "handover_port";
const STORAGE_OUTPUT_KEY = "handover_output_dir";
const DEFAULT_PORT = 7437;

// DOM refs
const btnExport = document.getElementById("btn-export");
const btnHandover = document.getElementById("btn-handover");
const statusExport = document.getElementById("status-export");
const statusHandover = document.getElementById("status-handover");
const outputDirInput = document.getElementById("output-dir");
const portInput = document.getElementById("port");

// ─── helpers ──────────────────────────────────────────────────────────────────

function showStatus(el, message, type) {
  el.textContent = message;
  el.className = `status ${type}`;
}

function setLoading(btn, loading, defaultLabel) {
  btn.disabled = loading;
  btn.textContent = loading ? "Working…" : defaultLabel;
}

function saveSettings() {
  chrome.storage.local.set({
    [STORAGE_PORT_KEY]: parseInt(portInput.value, 10) || DEFAULT_PORT,
    [STORAGE_OUTPUT_KEY]: outputDirInput.value.trim(),
  });
}

/** Get the active tab in the current window. */
async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab || null;
}

/** Return true if the URL is a supported chat page. */
function isSupportedPage(url) {
  if (!url) return false;
  return (
    url.includes("claude.ai/chat/") ||
    url.includes("claude.ai/project/") ||
    url.includes("chat.openai.com/")
  );
}

// ─── Restore saved settings ───────────────────────────────────────────────────

chrome.storage.local.get([STORAGE_PORT_KEY, STORAGE_OUTPUT_KEY], (items) => {
  if (items[STORAGE_PORT_KEY]) portInput.value = items[STORAGE_PORT_KEY];
  if (items[STORAGE_OUTPUT_KEY]) outputDirInput.value = items[STORAGE_OUTPUT_KEY];
});

outputDirInput.addEventListener("change", saveSettings);
portInput.addEventListener("change", saveSettings);

// ─── Export Chat as JSON ──────────────────────────────────────────────────────

btnExport.addEventListener("click", async () => {
  setLoading(btnExport, true, "Export Chat as JSON");
  showStatus(statusExport, "Fetching conversation from claude.ai API…", "info");

  try {
    const tab = await getActiveTab();
    if (!tab?.id) {
      showStatus(statusExport, "Could not determine active tab.", "error");
      return;
    }
    if (!isSupportedPage(tab.url)) {
      showStatus(
        statusExport,
        "Navigate to a claude.ai/chat/ page first.",
        "error"
      );
      return;
    }

    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: "export", tabId: tab.id },
        (resp) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(resp);
          }
        }
      );
    });

    if (response.success) {
      const { filename, messageCount, title } = response.result;
      // Show download confirmation + CLI command
      showStatus(
        statusExport,
        `Downloaded ${filename} (${messageCount} messages)`,
        "success"
      );
      // Append CLI hint below the status
      const hint = document.createElement("div");
      hint.className = "cli-hint";
      hint.innerHTML =
        `Run in terminal:<br>` +
        `<code>handover --input ~/Downloads/${filename} --output ./my-project/ --no-llm</code>`;
      // Replace any previous hint
      const prev = document.querySelector(".cli-hint");
      if (prev) prev.remove();
      statusExport.after(hint);
    } else {
      showStatus(statusExport, response.error || "Export failed.", "error");
    }
  } catch (err) {
    showStatus(statusExport, err.message || "Unexpected error.", "error");
  } finally {
    setLoading(btnExport, false, "Export Chat as JSON");
  }
});

// ─── Send to Claude Code (live pipeline) ─────────────────────────────────────

btnHandover.addEventListener("click", async () => {
  saveSettings();
  setLoading(btnHandover, true, "Send to Claude Code");
  showStatus(statusHandover, "Extracting conversation…", "info");

  try {
    const tab = await getActiveTab();
    if (!tab?.id) {
      showStatus(statusHandover, "Could not determine active tab.", "error");
      return;
    }
    if (!isSupportedPage(tab.url)) {
      showStatus(
        statusHandover,
        "Navigate to a claude.ai or chat.openai.com page first.",
        "error"
      );
      return;
    }

    showStatus(statusHandover, "Running handover pipeline…", "info");

    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: "handover", tabId: tab.id },
        (resp) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(resp);
          }
        }
      );
    });

    if (response.success) {
      showStatus(
        statusHandover,
        `Done — CLAUDE.md written to ${response.result.claude_md}`,
        "success"
      );
    } else {
      showStatus(statusHandover, response.error || "Unknown error.", "error");
    }
  } catch (err) {
    showStatus(statusHandover, err.message || "Unexpected error.", "error");
  } finally {
    setLoading(btnHandover, false, "Send to Claude Code");
  }
});
