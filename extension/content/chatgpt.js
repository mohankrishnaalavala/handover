/**
 * content/chatgpt.js
 * Extracts conversation messages from chat.openai.com and sends them to background.js.
 *
 * Called by popup.js via chrome.tabs.sendMessage({ action: "extract" }).
 * DOM selectors validated against chat.openai.com as of 2026-04.
 * Re-validate selectors when OpenAI updates its frontend.
 */

(function () {
  "use strict";

  /**
   * Extract all messages from the current ChatGPT conversation page.
   * @returns {{ source: string, conversation: Object }|null}
   */
  function extractConversation() {
    // ChatGPT message containers carry a data-message-author-role attribute
    const messageDivs = document.querySelectorAll(
      "[data-message-author-role]"
    );

    if (messageDivs.length === 0) {
      return null;
    }

    const messages = Array.from(messageDivs).map((el) => {
      const role = el.getAttribute("data-message-author-role") || "user";
      // The actual text content lives inside .markdown or the element itself
      const contentEl = el.querySelector(".markdown") || el;
      const content = (contentEl.innerText || contentEl.textContent || "").trim();
      return {
        role: role === "user" ? "user" : "assistant",
        content,
      };
    });

    // Try to get conversation title from the sidebar active link
    const activeLink = document.querySelector('nav a[class*="active"]');
    const title = activeLink
      ? (activeLink.innerText || "").trim()
      : document.title.replace(" - ChatGPT", "").trim();

    // Attempt to read conversation ID from the URL (/c/<id>)
    const urlMatch = window.location.pathname.match(/\/c\/([^/]+)/);
    const conversationId = urlMatch ? urlMatch[1] : "";

    return {
      source: "chatgpt",
      conversation: {
        id: conversationId,
        title: title || "Untitled conversation",
        mapping: null, // not reconstructed from DOM — use export for full fidelity
        messages,
      },
    };
  }

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "extract") {
      const result = extractConversation();
      if (!result) {
        sendResponse({
          success: false,
          error:
            "No conversation found. Make sure you are on a chat.openai.com conversation page.",
        });
      } else {
        sendResponse({ success: true, data: result });
      }
    }
    return true;
  });
})();
