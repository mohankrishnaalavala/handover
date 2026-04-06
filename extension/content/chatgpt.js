/**
 * content/chatgpt.js
 *
 * Two responsibilities:
 *   "export"  — fetch the full conversation from ChatGPT's internal REST API
 *               and return it in handover's expected format for CLI use.
 *   "extract" — used by the "Send to Claude Code" live-pipeline flow.
 *               Tries API first, falls back to DOM scraping.
 *
 * ChatGPT internal API (same-origin, session cookies apply automatically):
 *   GET /backend-api/conversations?offset=0&limit=1  → find most recent
 *   GET /backend-api/conversation/<id>               → full conversation with messages
 *
 * The API response has a "mapping" object (keyed by message UUID).
 * We walk the linked list from the last node back to root to reconstruct order.
 */

(function () {
  "use strict";

  // ─── helpers ──────────────────────────────────────────────────────────────

  function getConvId() {
    // URL pattern: /c/<conversation-id>
    const m = window.location.pathname.match(/\/c\/([^/?#]+)/);
    return m ? m[1] : null;
  }

  // ─── Strategy 0: ChatGPT internal REST API (primary) ──────────────────────

  async function fetchViaAPI() {
    const convId = getConvId();
    if (!convId) return null;

    try {
      const resp = await fetch(`/backend-api/conversation/${convId}`, {
        credentials: "include",
      });
      if (!resp.ok) return null;
      const data = await resp.json();

      // data.mapping: { [uuid]: { id, message: { author, content }, parent, children } }
      const mapping = data.mapping || {};

      // Walk the tree: find root node, then follow children to reconstruct order
      // Root node has no parent or parent === null
      const nodes = Object.values(mapping);
      const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));

      // Find root
      const root = nodes.find((n) => !n.parent || !nodeById[n.parent]);
      if (!root) return null;

      // BFS/DFS to collect messages in order
      const messages = [];
      const visited = new Set();

      function walk(nodeId) {
        if (!nodeId || visited.has(nodeId)) return;
        visited.add(nodeId);
        const node = nodeById[nodeId];
        if (!node) return;

        const msg = node.message;
        if (msg && msg.content) {
          const role = msg.author?.role;
          if (role === "user" || role === "assistant") {
            // content.parts is an array of strings or objects
            const parts = msg.content.parts || [];
            const text = parts
              .map((p) => (typeof p === "string" ? p : p?.text || ""))
              .join("\n")
              .trim();
            if (text.length > 0) {
              messages.push({
                sender: role === "user" ? "human" : "assistant",
                text,
                created_at: msg.create_time
                  ? new Date(msg.create_time * 1000).toISOString()
                  : undefined,
              });
            }
          }
        }

        // Follow the first (main) child — handles linear conversations
        // For branched conversations, take the last child (most recent branch)
        const children = node.children || [];
        if (children.length > 0) {
          walk(children[children.length - 1]);
        }
      }

      walk(root.id);

      if (messages.length === 0) return null;

      return {
        // Use claude-compatible format so ClaudeParser handles it
        uuid: convId,
        name: data.title || "Untitled conversation",
        chat_messages: messages,
      };
    } catch (_) {
      return null;
    }
  }

  // ─── DOM fallback ──────────────────────────────────────────────────────────

  function domFallback() {
    const messageDivs = document.querySelectorAll("[data-message-author-role]");
    if (messageDivs.length === 0) return null;

    const messages = Array.from(messageDivs)
      .map((el) => {
        const role = el.getAttribute("data-message-author-role") || "user";
        const contentEl = el.querySelector(".markdown") || el;
        const text = (contentEl.innerText || contentEl.textContent || "").trim();
        return { sender: role === "user" ? "human" : "assistant", text };
      })
      .filter((m) => m.text.length > 5);

    const hasHuman = messages.some((m) => m.sender === "human");
    const hasAsst = messages.some((m) => m.sender === "assistant");
    return hasHuman && hasAsst ? messages : null;
  }

  // ─── Title + ID helpers ────────────────────────────────────────────────────

  function getTitle() {
    const activeLink = document.querySelector('nav a[class*="active"]');
    return activeLink
      ? (activeLink.innerText || "").trim()
      : document.title.replace(/\s*[-–|]\s*ChatGPT\s*$/, "").trim();
  }

  // ─── Message listener ──────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {

    // ── "export" action: fetch via API, return full conversation JSON ──────
    if (request.action === "export") {
      const convId = getConvId();
      if (!convId) {
        sendResponse({
          success: false,
          error: "No conversation found in URL. Open a chat.openai.com/c/<id> page first.",
        });
        return true;
      }

      fetchViaAPI().then((conv) => {
        if (!conv) {
          sendResponse({
            success: false,
            error:
              "Could not fetch conversation from ChatGPT API. " +
              "Make sure you are logged in and on a /c/ conversation page.",
          });
          return;
        }
        sendResponse({ success: true, data: conv });
      });

      return true;
    }

    // ── "extract" action: API first, DOM fallback ──────────────────────────
    if (request.action === "extract") {
      const convId = getConvId();
      if (!convId) {
        sendResponse({
          success: false,
          error: "Navigate to a chat.openai.com/c/ conversation first.",
        });
        return true;
      }

      fetchViaAPI().then((conv) => {
        if (conv) {
          sendResponse({
            success: true,
            data: { source: "chatgpt", conversation: conv },
          });
          return;
        }

        const domMessages = domFallback();
        if (!domMessages) {
          sendResponse({
            success: false,
            error: "Could not extract conversation. Try 'Export Chat as JSON' instead.",
          });
          return;
        }

        sendResponse({
          success: true,
          data: {
            source: "chatgpt",
            conversation: {
              uuid: convId,
              name: getTitle() || "Untitled conversation",
              chat_messages: domMessages,
            },
          },
        });
      });

      return true;
    }

    return false;
  });
})();
