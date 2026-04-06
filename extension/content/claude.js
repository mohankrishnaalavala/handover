/**
 * content/claude.js
 *
 * Two responsibilities:
 *   1. "export"  — fetch the full conversation from claude.ai's internal REST API
 *                  and return it as structured JSON ready for the handover CLI.
 *   2. "extract" — legacy: attempt DOM extraction (used only if API fetch fails,
 *                  or for the "Send to Claude Code" live-pipeline flow).
 *
 * Why API-first?
 *   claude.ai is a React SPA. Its DOM structure changes with every deploy.
 *   The internal REST API is far more stable and returns the full untruncated text
 *   of every message (human + assistant), including all markdown.
 *
 * API endpoints used (same-origin, browser session cookies apply automatically):
 *   GET /api/organizations                                    → [{ uuid, ... }]
 *   GET /api/organizations/{org}/chat_conversations/{uuid}    → full conversation
 */

(function () {
  "use strict";

  // ─── helpers ──────────────────────────────────────────────────────────────

  /** Extract the conversation UUID from the current URL. */
  function getConvUUID() {
    const m = window.location.pathname.match(
      /\/chat\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i
    );
    return m ? m[1] : null;
  }

  // ─── Strategy 0: claude.ai internal REST API (primary) ────────────────────

  /**
   * Fetch the full conversation using claude.ai's own API.
   * Returns the conversation object in handover's expected format, or null on failure.
   */
  async function fetchViaAPI() {
    const convUUID = getConvUUID();
    if (!convUUID) return null;

    try {
      // Step 1: get org UUID
      const orgsResp = await fetch("/api/organizations", { credentials: "include" });
      if (!orgsResp.ok) return null;
      const orgs = await orgsResp.json();
      if (!Array.isArray(orgs) || orgs.length === 0) return null;
      const orgUUID = orgs[0].uuid;

      // Step 2: fetch conversation
      const convResp = await fetch(
        `/api/organizations/${orgUUID}/chat_conversations/${convUUID}`,
        { credentials: "include" }
      );
      if (!convResp.ok) return null;
      const conv = await convResp.json();

      // conv.chat_messages is already [{sender, text, uuid, created_at}]
      // which is exactly the format ClaudeParser expects.
      const messages = (conv.chat_messages || []).filter(
        (m) => m.text && m.text.trim().length > 0
      );

      if (messages.length === 0) return null;

      return {
        uuid: conv.uuid || convUUID,
        name: conv.name || "Untitled conversation",
        chat_messages: messages.map((m) => ({
          uuid: m.uuid,
          sender: m.sender,          // "human" | "assistant"
          text: m.text,
          created_at: m.created_at,
        })),
      };
    } catch (_) {
      return null;
    }
  }

  // ─── Strategy 1-N: DOM fallback (for extract action only) ─────────────────

  function textOf(el) {
    return (el.innerText || el.textContent || "").trim();
  }

  function domFallback() {
    const PAIRS = [
      // [selector, sender]
      ['[data-testid="human-turn"]', "human"],
      ['[data-testid="ai-turn"]', "assistant"],
      ['[data-message-author-role="user"]', "human"],
      ['[data-message-author-role="assistant"]', "assistant"],
    ];

    const seen = new WeakSet();
    const items = [];

    for (const [sel, sender] of PAIRS) {
      for (const el of document.querySelectorAll(sel)) {
        if (!seen.has(el)) {
          seen.add(el);
          items.push({ el, sender });
        }
      }
    }

    if (items.length === 0) return null;

    // Sort by DOM order
    items.sort((a, b) => {
      const rel = a.el.compareDocumentPosition(b.el);
      if (rel & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
      if (rel & Node.DOCUMENT_POSITION_PRECEDING) return 1;
      return 0;
    });

    const messages = items
      .map(({ el, sender }) => ({ sender, text: textOf(el) }))
      .filter((m) => m.text.length > 5);

    const hasHuman = messages.some((m) => m.sender === "human");
    const hasAsst = messages.some((m) => m.sender === "assistant");
    return hasHuman && hasAsst ? messages : null;
  }

  // ─── Message listener ──────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {

    // ── "export" action: fetch via API, return full conversation JSON ──────
    if (request.action === "export") {
      const convUUID = getConvUUID();
      if (!convUUID) {
        sendResponse({
          success: false,
          error: "No conversation found in URL. Open a claude.ai/chat/<id> page first.",
        });
        return true;
      }

      fetchViaAPI().then((conv) => {
        if (!conv) {
          sendResponse({
            success: false,
            error:
              "Could not fetch conversation from claude.ai API. " +
              "Make sure you are logged in and on a /chat/ page.",
          });
          return;
        }
        sendResponse({ success: true, data: conv });
      });

      return true; // keep channel open for async response
    }

    // ── "extract" action: try API first, fall back to DOM (for live pipeline) ─
    if (request.action === "extract") {
      const convUUID = getConvUUID();
      if (!convUUID) {
        sendResponse({
          success: false,
          error: "No conversation found. Navigate to a claude.ai/chat/ page first.",
        });
        return true;
      }

      fetchViaAPI().then((conv) => {
        if (conv) {
          sendResponse({
            success: true,
            data: {
              source: "claude",
              conversation: conv,
            },
          });
          return;
        }

        // API failed — fall back to DOM
        const domMessages = domFallback();
        if (!domMessages) {
          sendResponse({
            success: false,
            error:
              "Could not extract conversation. " +
              "Try 'Export Chat as JSON' instead — it uses the claude.ai API directly.",
          });
          return;
        }

        sendResponse({
          success: true,
          data: {
            source: "claude",
            conversation: {
              uuid: convUUID,
              name:
                (document.querySelector("h1") || {}).innerText ||
                "Untitled conversation",
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
