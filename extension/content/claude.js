/**
 * content/claude.js
 * Extracts conversation messages from claude.ai and sends them to background.js.
 *
 * Architecture: rather than betting on a single set of selectors (which break when
 * claude.ai ships a frontend update), this script tries many strategies in order
 * and returns the first one that produces BOTH human and assistant messages.
 *
 * Strategies (in priority order):
 *   A. Explicit role attributes / data-testid (exact matches)
 *   B. Role-containing class names (loose matches)
 *   C. Find the conversation scroll container, walk its children
 *   D. Prose + sibling analysis (Claude renders responses in .prose wrappers)
 *   E. Nuclear fallback: read all paragraph text in document order
 */

(function () {
  "use strict";

  // ─── helpers ──────────────────────────────────────────────────────────────

  function textOf(el) {
    return (el.innerText || el.textContent || "").trim();
  }

  /** Return document-order comparison (-1 | 0 | 1) */
  function domOrder(a, b) {
    const rel = a.compareDocumentPosition(b);
    if (rel & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
    if (rel & Node.DOCUMENT_POSITION_PRECEDING) return 1;
    return 0;
  }

  /**
   * Remove elements that are ancestors of other elements in the list.
   * Keeps the most specific (deepest) match when selectors overlap.
   */
  function dedupeAncestors(elements) {
    return elements.filter(
      (el) => !elements.some((other) => other !== el && el.contains(other))
    );
  }

  /** Build message list from {el, sender} pairs, sorted by DOM position. */
  function toMessages(pairs) {
    return pairs
      .sort((a, b) => domOrder(a.el, b.el))
      .map(({ el, sender }) => ({ sender, text: textOf(el) }))
      .filter((m) => m.text.length > 5);
  }

  // ─── Strategy A: explicit role attribute or data-testid ───────────────────

  function strategyA() {
    const HUMAN_SELS = [
      '[data-testid="user-human-turn"]',
      '[data-testid="human-turn"]',
      '[data-message-author-role="user"]',
      '[data-message-author-role="human"]',
    ];
    const ASST_SELS = [
      '[data-testid="assistant-turn"]',
      '[data-testid="ai-turn"]',
      '[data-message-author-role="assistant"]',
    ];

    const seen = new WeakSet();
    const pairs = [];

    for (const [sels, sender] of [[HUMAN_SELS, "human"], [ASST_SELS, "assistant"]]) {
      for (const sel of sels) {
        for (const el of document.querySelectorAll(sel)) {
          if (!seen.has(el)) { seen.add(el); pairs.push({ el, sender }); }
        }
      }
    }

    const msgs = toMessages(pairs);
    const hasHuman = msgs.some((m) => m.sender === "human");
    const hasAsst = msgs.some((m) => m.sender === "assistant");
    return hasHuman && hasAsst ? msgs : null;
  }

  // ─── Strategy B: class-name heuristics ────────────────────────────────────

  function strategyB() {
    const HUMAN_SELS = [
      '[class*="human-turn"]', '[class*="user-turn"]',
      '[class*="UserMessage"]', '[class*="user-message"]',
      '[class*="HumanMessage"]', '[class*="human-message"]',
      '[class*="user-bubble"]', '[class*="human-bubble"]',
    ];
    const ASST_SELS = [
      '[class*="ai-turn"]', '[class*="assistant-turn"]',
      '[class*="AssistantMessage"]', '[class*="assistant-message"]',
      '[class*="ClaudeMessage"]', '[class*="claude-message"]',
      '[class*="ai-message"]', '[class*="bot-message"]',
    ];

    const seen = new WeakSet();
    const pairs = [];

    for (const [sels, sender] of [[HUMAN_SELS, "human"], [ASST_SELS, "assistant"]]) {
      for (const sel of sels) {
        for (const el of document.querySelectorAll(sel)) {
          if (!seen.has(el)) { seen.add(el); pairs.push({ el, sender }); }
        }
      }
    }

    const msgs = toMessages(pairs);
    const hasHuman = msgs.some((m) => m.sender === "human");
    const hasAsst = msgs.some((m) => m.sender === "assistant");
    return hasHuman && hasAsst ? msgs : null;
  }

  // ─── Strategy C: walk the conversation container's children ───────────────

  function strategyC() {
    // Find the element most likely to be the conversation scroll container
    const CONTAINER_SELS = [
      '[data-testid="conversation-turn-list"]',
      '[class*="conversation-content"]',
      '[class*="ConversationContent"]',
      '[class*="chat-messages"]',
      '[class*="ChatMessages"]',
      '[class*="message-list"]',
      'main [role="log"]',
      'main > div[class]',
    ];

    let container = null;
    for (const sel of CONTAINER_SELS) {
      const el = document.querySelector(sel);
      if (el && el.children.length >= 2) { container = el; break; }
    }
    if (!container) return null;

    // Walk direct children; assign role based on their content
    const children = Array.from(container.children).filter(
      (el) => textOf(el).length > 10
    );
    if (children.length < 2) return null;

    const pairs = children.map((el) => {
      const cls = (el.className || "").toLowerCase();
      const tid = (el.getAttribute("data-testid") || "").toLowerCase();
      const role = el.getAttribute("data-message-author-role") || "";

      let sender = "unknown";
      if (role === "user" || tid.includes("human") || tid.includes("user") ||
          cls.includes("human") || cls.includes("user")) {
        sender = "human";
      } else if (role === "assistant" || tid.includes("assistant") || tid.includes("ai") ||
                 cls.includes("assistant") || cls.includes("claude") || cls.includes("ai")) {
        sender = "assistant";
      }
      return { el, sender };
    });

    const known = pairs.filter((p) => p.sender !== "unknown");
    const msgs = toMessages(known);
    const hasHuman = msgs.some((m) => m.sender === "human");
    const hasAsst = msgs.some((m) => m.sender === "assistant");
    return hasHuman && hasAsst ? msgs : null;
  }

  // ─── Strategy D: prose-based (Claude renders responses as .prose) ──────────

  function strategyD() {
    // Claude always renders its markdown responses in a .prose wrapper.
    // User messages are often in a plain div with no special class.
    // Find all prose elements (assistant), then try to find their adjacent
    // sibling or nearby non-prose element (human).

    const proseEls = dedupeAncestors(
      Array.from(document.querySelectorAll(".prose, [class*='prose']")).filter(
        (el) => textOf(el).length > 20
      )
    );
    if (proseEls.length === 0) return null;

    const pairs = [];
    const seen = new WeakSet();

    for (const prose of proseEls) {
      // The human message is typically a sibling/cousin of the prose element
      // Walk up at most 4 levels to find a parent that has another sibling
      let parent = prose.parentElement;
      for (let i = 0; i < 4 && parent; i++) {
        const siblings = Array.from(parent.parentElement?.children || []).filter(
          (s) => s !== parent && textOf(s).length > 10
        );
        if (siblings.length > 0) {
          for (const sib of siblings) {
            if (!seen.has(sib)) {
              seen.add(sib);
              pairs.push({ el: sib, sender: "human" });
            }
          }
          break;
        }
        parent = parent.parentElement;
      }
      if (!seen.has(prose)) {
        seen.add(prose);
        pairs.push({ el: prose, sender: "assistant" });
      }
    }

    const msgs = toMessages(pairs);
    const hasHuman = msgs.some((m) => m.sender === "human");
    const hasAsst = msgs.some((m) => m.sender === "assistant");
    return hasHuman && hasAsst ? msgs : null;
  }

  // ─── Strategy E: nuclear — read every paragraph/heading in document order ──

  function strategyE() {
    // Collect all text blocks from the main content area in DOM order.
    // Assign roles by alternating: assume user→assistant→user→assistant.
    const main = document.querySelector("main") || document.body;
    const blocks = Array.from(
      main.querySelectorAll("p, h1, h2, h3, h4, li, blockquote, pre, [class*='text']")
    ).filter((el) => {
      if (el.closest("nav, header, footer, aside, [role='navigation']")) return false;
      return textOf(el).length > 15;
    });

    if (blocks.length < 2) return null;

    // Group adjacent blocks under the same top-level parent into one "turn"
    const turns = [];
    let currentParent = null;
    let currentTexts = [];

    for (const block of blocks) {
      // Find a stable "turn" ancestor (2–4 levels up from the text node)
      let ancestor = block.parentElement;
      for (let i = 0; i < 3 && ancestor && ancestor !== main; i++) {
        ancestor = ancestor.parentElement;
      }
      if (ancestor !== currentParent) {
        if (currentTexts.length > 0) {
          turns.push(currentTexts.join("\n").trim());
        }
        currentParent = ancestor;
        currentTexts = [textOf(block)];
      } else {
        currentTexts.push(textOf(block));
      }
    }
    if (currentTexts.length > 0) turns.push(currentTexts.join("\n").trim());

    if (turns.length < 2) return null;

    // Assign alternating roles
    return turns
      .filter((t) => t.length > 5)
      .map((text, idx) => ({ sender: idx % 2 === 0 ? "human" : "assistant", text }));
  }

  // ─── Title extraction ──────────────────────────────────────────────────────

  function extractTitle() {
    const TITLE_SELS = [
      '[data-testid="conversation-title"]',
      '[class*="conversation-title"]',
      '[class*="ConversationTitle"]',
      '[class*="chat-title"]',
      "h1",
      "title",
    ];
    for (const sel of TITLE_SELS) {
      const el = document.querySelector(sel);
      if (!el) continue;
      const t = (el.value || el.innerText || el.textContent || "").trim();
      if (t && t !== "Claude" && t !== "New chat") return t;
    }
    return "";
  }

  // ─── UUID extraction ───────────────────────────────────────────────────────

  function extractUUID() {
    // URL path: /chat/<uuid> or /project/<id>/chat/<uuid>
    const match = window.location.pathname.match(
      /\/chat\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i
    );
    return match ? match[1] : "";
  }

  // ─── Main ──────────────────────────────────────────────────────────────────

  function extractConversation() {
    const url = window.location.href;
    const onChatPage = url.includes("claude.ai/chat/") || url.includes("claude.ai/project/");

    const messages =
      strategyA() ||
      strategyB() ||
      strategyC() ||
      strategyD() ||
      strategyE();

    if (!messages || messages.length === 0) {
      return {
        success: false,
        error: onChatPage
          ? "Could not extract messages. Open DevTools console on this page, run: " +
            "document.querySelectorAll('[data-testid]').length " +
            "and report the result at github.com/mohankrishnaalavala/handover/issues"
          : "No conversation found. Navigate to a claude.ai chat first.",
      };
    }

    // Deduplicate consecutive identical messages
    const deduped = messages.reduce((acc, msg) => {
      const prev = acc[acc.length - 1];
      if (prev && prev.sender === msg.sender && prev.text === msg.text) return acc;
      return [...acc, msg];
    }, []);

    return {
      success: true,
      data: {
        source: "claude",
        conversation: {
          uuid: extractUUID(),
          name: extractTitle() || "Untitled conversation",
          chat_messages: deduped,
        },
      },
    };
  }

  // ─── Message listener ──────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "extract") {
      sendResponse(extractConversation());
    }
    // For "debug": return what each strategy found — useful for diagnosing selector breaks
    if (request.action === "debug") {
      sendResponse({
        url: window.location.href,
        title: extractTitle(),
        strategyA: strategyA()?.length ?? "null",
        strategyB: strategyB()?.length ?? "null",
        strategyC: strategyC()?.length ?? "null",
        strategyD: strategyD()?.length ?? "null",
        strategyE: strategyE()?.length ?? "null",
        testIdCount: document.querySelectorAll("[data-testid]").length,
        roleCount: document.querySelectorAll("[data-message-author-role]").length,
        proseCount: document.querySelectorAll(".prose, [class*='prose']").length,
      });
    }
    return true;
  });
})();
