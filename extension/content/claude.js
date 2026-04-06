/**
 * content/claude.js
 * Extracts conversation messages from claude.ai and sends them to background.js.
 *
 * Called by popup.js via chrome.tabs.sendMessage({ action: "extract" }).
 * DOM selectors validated against claude.ai as of 2026-04.
 * Re-validate selectors when Claude updates its frontend.
 */

(function () {
  "use strict";

  /**
   * Extract all messages from the current claude.ai conversation page.
   * @returns {{ source: string, conversation: Object }|null}
   */
  function extractConversation() {
    // Human turns
    const humanTurns = document.querySelectorAll('[data-testid="human-turn"]');
    // AI turns
    const aiTurns = document.querySelectorAll('[data-testid="ai-turn"]');

    if (humanTurns.length === 0 && aiTurns.length === 0) {
      return null;
    }

    // Build an ordered list by walking the DOM — interleaved human/ai turns
    const allTurns = Array.from(
      document.querySelectorAll(
        '[data-testid="human-turn"], [data-testid="ai-turn"]'
      )
    );

    const messages = allTurns.map((el) => {
      const isHuman = el.getAttribute("data-testid") === "human-turn";
      // Extract visible text content, stripping code block wrappers minimally
      const content = el.innerText || el.textContent || "";
      return {
        sender: isHuman ? "human" : "assistant",
        text: content.trim(),
      };
    });

    // Try to get conversation title from the page heading
    const titleEl =
      document.querySelector('[data-testid="conversation-title"]') ||
      document.querySelector("h1") ||
      document.querySelector("title");
    const title = titleEl ? (titleEl.value || titleEl.innerText || "").trim() : "";

    return {
      source: "claude",
      conversation: {
        uuid: window.location.pathname.split("/").pop() || "",
        name: title || "Untitled conversation",
        chat_messages: messages,
      },
    };
  }

  // Listen for messages from popup.js / background.js
  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "extract") {
      const result = extractConversation();
      if (!result) {
        sendResponse({
          success: false,
          error:
            "No conversation found. Make sure you are on a claude.ai chat page.",
        });
      } else {
        sendResponse({ success: true, data: result });
      }
    }
    return true; // keep message channel open for async response
  });
})();
