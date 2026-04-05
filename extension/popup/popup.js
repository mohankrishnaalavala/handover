/**
 * popup.js — handover Chrome extension popup
 *
 * Reads output dir + port from storage, sends { action: "handover", tabId }
 * to background.js, shows result/error in the status div.
 */

"use strict";

const STORAGE_PORT_KEY = "handover_port";
const STORAGE_OUTPUT_KEY = "handover_output_dir";
const DEFAULT_PORT = 7437;

// DOM refs
const btnHandover = document.getElementById("btn-handover");
const statusDiv = document.getElementById("status");
const outputDirInput = document.getElementById("output-dir");
const portInput = document.getElementById("port");

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function showStatus(message, type) {
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
}

function setLoading(loading) {
  btnHandover.disabled = loading;
  btnHandover.textContent = loading ? "Sending…" : "Send to Claude Code";
}

function saveSettings() {
  chrome.storage.local.set({
    [STORAGE_PORT_KEY]: parseInt(portInput.value, 10) || DEFAULT_PORT,
    [STORAGE_OUTPUT_KEY]: outputDirInput.value.trim(),
  });
}

// ------------------------------------------------------------------
// Init — restore saved settings
// ------------------------------------------------------------------

chrome.storage.local.get([STORAGE_PORT_KEY, STORAGE_OUTPUT_KEY], (items) => {
  if (items[STORAGE_PORT_KEY]) {
    portInput.value = items[STORAGE_PORT_KEY];
  }
  if (items[STORAGE_OUTPUT_KEY]) {
    outputDirInput.value = items[STORAGE_OUTPUT_KEY];
  }
});

outputDirInput.addEventListener("change", saveSettings);
portInput.addEventListener("change", saveSettings);

// ------------------------------------------------------------------
// Main action
// ------------------------------------------------------------------

btnHandover.addEventListener("click", async () => {
  saveSettings();
  setLoading(true);
  showStatus("Extracting conversation…", "info");

  try {
    // Get the active tab in the current window
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      showStatus("Could not determine active tab.", "error");
      setLoading(false);
      return;
    }

    // Supported hosts
    const supportedHosts = ["claude.ai", "chat.openai.com"];
    const tabHost = tab.url ? new URL(tab.url).hostname : "";
    if (!supportedHosts.some((h) => tabHost.endsWith(h))) {
      showStatus(
        `Unsupported page. Navigate to claude.ai or chat.openai.com first.`,
        "error"
      );
      setLoading(false);
      return;
    }

    showStatus("Running handover pipeline…", "info");

    // Delegate extraction + HTTP call to background service worker
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
        `Done — CLAUDE.md written to ${response.result.claude_md}`,
        "success"
      );
    } else {
      showStatus(response.error || "Unknown error.", "error");
    }
  } catch (err) {
    showStatus(err.message || "Unexpected error.", "error");
  } finally {
    setLoading(false);
  }
});
