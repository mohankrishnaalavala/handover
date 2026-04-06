/**
 * background.js — MV3 service worker
 *
 * Flow:
 *   popup.js  ──sendMessage──▶  background.js  ──fetch──▶  localhost:7437/handover
 *                                                               │
 *                               ◀──result/error──────────────────
 *   popup.js  ◀──sendResponse──
 */

"use strict";

const HANDOVER_PORT_KEY = "handover_port";
const HANDOVER_OUTPUT_KEY = "handover_output_dir";
const DEFAULT_PORT = 7437;

/**
 * Get the configured port and output directory from storage.
 * @returns {Promise<{port: number, outputDir: string}>}
 */
async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      [HANDOVER_PORT_KEY, HANDOVER_OUTPUT_KEY],
      (items) => {
        resolve({
          port: items[HANDOVER_PORT_KEY] || DEFAULT_PORT,
          outputDir: items[HANDOVER_OUTPUT_KEY] || "",
        });
      }
    );
  });
}

/**
 * POST conversation data to the local handover server.
 * @param {number} port
 * @param {string} outputDir
 * @param {Object} payload  - { source, conversation }
 * @returns {Promise<Object>} - server response JSON
 */
async function postToServer(port, outputDir, payload) {
  // If an output directory is set, update the server config first
  if (outputDir) {
    try {
      await fetch(`http://localhost:${port}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: outputDir }),
      });
    } catch (_) {
      // Non-fatal — server may still use its default config
    }
  }

  const resp = await fetch(`http://localhost:${port}/handover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.message || `Server error ${resp.status}`);
  }
  return data;
}

/**
 * Ask the active tab's content script to extract the conversation.
 * @param {number} tabId
 * @returns {Promise<{source: string, conversation: Object}>}
 */
function extractFromTab(tabId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, { action: "extract" }, (response) => {
      if (chrome.runtime.lastError) {
        reject(
          new Error(
            chrome.runtime.lastError.message ||
              "Could not contact content script. Refresh the page and try again."
          )
        );
        return;
      }
      if (!response || !response.success) {
        reject(new Error(response?.error || "Extraction failed"));
        return;
      }
      resolve(response.data);
    });
  });
}

// ------------------------------------------------------------------
// Message listener — called by popup.js
// ------------------------------------------------------------------

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action !== "handover") {
    return false;
  }

  const { tabId } = request;

  (async () => {
    try {
      const { port, outputDir } = await getConfig();

      // 1. Extract conversation from the active tab
      const payload = await extractFromTab(tabId);

      // 2. POST to local server
      const result = await postToServer(port, outputDir, payload);

      sendResponse({ success: true, result });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const isServerDown =
        message.includes("Failed to fetch") ||
        message.includes("NetworkError") ||
        message.includes("ECONNREFUSED");

      sendResponse({
        success: false,
        error: isServerDown
          ? `Cannot reach handover server on port ${DEFAULT_PORT}. Run: handover serve`
          : message,
      });
    }
  })();

  return true; // keep the message channel open for async sendResponse
});
