/**
 * content/claude.js
 * Extracts conversation messages from claude.ai and sends them to background.js.
 *
 * Called by popup.js via chrome.tabs.sendMessage({ action: "extract" }).
 *
 * Uses multiple fallback selector strategies since claude.ai frequently updates its DOM.
 * Strategy order:
 *   1. data-testid="human-turn" / "ai-turn"    (legacy)
 *   2. [class*="human-turn"] / [class*="ai-turn"]  (class-based)
 *   3. [data-message-author-role]               (role attribute)
 *   4. Prose containers inside known wrappers
 */

(function () {
  "use strict";

  // -------------------------------------------------------------------
  // Selector strategies — tried in order until one yields messages
  // -------------------------------------------------------------------

  /** Strategy 1: legacy data-testid attributes */
  function tryTestId() {
    const turns = Array.from(
      document.querySelectorAll('[data-testid="human-turn"], [data-testid="ai-turn"]')
    );
    if (turns.length === 0) return null;
    return turns.map((el) => ({
      sender: el.getAttribute("data-testid") === "human-turn" ? "human" : "assistant",
      text: (el.innerText || el.textContent || "").trim(),
    }));
  }

  /** Strategy 2: class name contains "human-turn" or "ai-turn" */
  function tryClassTurn() {
    const turns = Array.from(
      document.querySelectorAll('[class*="human-turn"], [class*="ai-turn"]')
    );
    if (turns.length === 0) return null;
    return turns.map((el) => {
      const cls = el.className || "";
      const sender = cls.includes("human") ? "human" : "assistant";
      return { sender, text: (el.innerText || el.textContent || "").trim() };
    });
  }

  /** Strategy 3: data-message-author-role (newer claude.ai builds) */
  function tryAuthorRole() {
    const turns = Array.from(document.querySelectorAll("[data-message-author-role]"));
    if (turns.length === 0) return null;
    return turns.map((el) => {
      const role = el.getAttribute("data-message-author-role") || "";
      const sender = role === "user" ? "human" : "assistant";
      return { sender, text: (el.innerText || el.textContent || "").trim() };
    });
  }

  /** Strategy 4: look for alternating prose blocks inside chat scroll container */
  function tryProseBlocks() {
    // claude.ai wraps prose content in divs with "prose" in the class
    const proseBlocks = Array.from(document.querySelectorAll(".prose, [class*='prose']"));
    if (proseBlocks.length === 0) return null;

    // Walk up each prose block to find its nearest role indicator
    return proseBlocks.map((el, idx) => {
      // Odd-indexed blocks are typically user messages in a back-and-forth layout,
      // but we can't rely on position alone — label all as assistant and let the
      // server handle it, since having content is better than returning nothing.
      const parentText = el.closest("[class*='human'], [class*='user']") ? "human" : "assistant";
      return { sender: parentText, text: (el.innerText || el.textContent || "").trim() };
    }).filter((m) => m.text.length > 0);
  }

  /** Strategy 5: last-resort — grab all text blocks in the main content area */
  function tryContentArea() {
    // Main chat column selectors that claude.ai has used
    const container =
      document.querySelector('[data-testid="conversation-turn-list"]') ||
      document.querySelector('[class*="conversation"]') ||
      document.querySelector("main") ||
      document.body;

    // Find direct children that look like message blocks
    const blocks = Array.from(
      container.querySelectorAll(
        "div[class*='message'], div[class*='turn'], div[class*='chat']"
      )
    ).filter((el) => {
      const text = (el.innerText || "").trim();
      return text.length > 20; // skip tiny layout divs
    });

    if (blocks.length === 0) return null;

    return blocks.map((el, idx) => ({
      sender: idx % 2 === 0 ? "human" : "assistant",
      text: (el.innerText || el.textContent || "").trim(),
    }));
  }

  // -------------------------------------------------------------------
  // Title extraction
  // -------------------------------------------------------------------

  function extractTitle() {
    const candidates = [
      document.querySelector('[data-testid="conversation-title"]'),
      document.querySelector('[class*="conversation-title"]'),
      document.querySelector('[class*="chat-title"]'),
      document.querySelector("h1"),
      document.querySelector("title"),
    ];
    for (const el of candidates) {
      if (!el) continue;
      const text = (el.value || el.innerText || el.textContent || "").trim();
      if (text && text !== "Claude") return text;
    }
    return "";
  }

  // -------------------------------------------------------------------
  // Main extraction
  // -------------------------------------------------------------------

  function extractConversation() {
    // Confirm we're on a chat page by URL
    const url = window.location.href;
    const isChat =
      url.includes("claude.ai/chat/") ||
      url.includes("claude.ai/project/");

    // Run strategies in priority order
    const messages =
      tryTestId() ||
      tryAuthorRole() ||
      tryClassTurn() ||
      tryProseBlocks() ||
      tryContentArea();

    if (!messages || messages.length === 0) {
      return {
        success: false,
        error: isChat
          ? "Could not extract messages — claude.ai may have updated its DOM. " +
            "Please report this at github.com/mohankrishnaalavala/handover/issues"
          : "No conversation found. Make sure you are on a claude.ai chat page.",
      };
    }

    // Deduplicate consecutive identical messages (can happen with nested selectors)
    const deduped = messages.reduce((acc, msg) => {
      const prev = acc[acc.length - 1];
      if (prev && prev.sender === msg.sender && prev.text === msg.text) return acc;
      return [...acc, msg];
    }, []);

    const uuid = url.split("/").find((p) => p.match(/^[0-9a-f-]{36}$/i)) || "";

    return {
      success: true,
      data: {
        source: "claude",
        conversation: {
          uuid,
          name: extractTitle() || "Untitled conversation",
          chat_messages: deduped,
        },
      },
    };
  }

  // -------------------------------------------------------------------
  // Message listener
  // -------------------------------------------------------------------

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "extract") {
      const result = extractConversation();
      sendResponse(result);
    }
    return true; // keep channel open for async response
  });
})();
