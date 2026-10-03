/* Knowledge InSight — Guided Conversations.
 *
 * The prompt is stored once, as the text of the <pre> inside the collapsed
 * "Show the full prompt" panel. Every button reads it from there and builds
 * its URL at run time, so if a link format changes it changes here and
 * nowhere else.
 *
 * Two assistants get a button, because only two accept a prompt through a link:
 *
 *   Claude    https://claude.ai/new?q=   prefills — widely used, undocumented
 *   ChatGPT   https://chatgpt.com/?q=    prefills — widely used, undocumented
 *
 * Gemini, Copilot and the rest have no such parameter, so a button for them
 * would open an empty chat and look broken. Copy covers them instead.
 *
 * Because neither link format is documented, every button copies the prompt to
 * the clipboard before it opens the assistant. If a link stops prefilling, the
 * learner can paste without coming back for help.
 */
(function () {
  "use strict";

  var KI = window.KI;
  if (!KI) return;

  var PROVIDERS = {
    claude: {
      label: "Claude",
      prefills: true,
      url: function (encoded) { return "https://claude.ai/new?q=" + encoded; }
    },
    chatgpt: {
      label: "ChatGPT",
      prefills: true,
      url: function (encoded) { return "https://chatgpt.com/?q=" + encoded; }
    },
    "claude-app": {
      label: "Claude desktop app",
      prefills: true,
      url: function (encoded) { return "claude://claude.ai/new?q=" + encoded; }
    }
  };

  KI.$$("[data-dialogue]").forEach(function (root) {
    var pre = root.querySelector("[data-prompt-text]");
    if (!pre) return;

    var prompt = pre.textContent.replace(/\s+$/, "");
    var encoded = encodeURIComponent(prompt);
    var status = root.querySelector("[data-dialogue-status]");
    var defaultNote = status ? status.innerHTML : "";

    function say(message, tone) {
      if (!status) return;
      status.innerHTML = message;
      status.classList.toggle("is-ok", tone === "ok");
      status.classList.toggle("is-warn", tone === "warn");
    }

    KI.$$("[data-provider]", root).forEach(function (link) {
      var provider = PROVIDERS[link.getAttribute("data-provider")];
      if (!provider) return;
      link.href = provider.url(encoded);

      link.addEventListener("click", function () {
        // Copy first, so a link that stops prefilling is still usable.
        KI.copy(prompt).then(function (copied) {
          if (provider.prefills) {
            say(copied
              ? "Opening " + provider.label + " with the prompt filled in. Press send to start. " +
                "The prompt is also on your clipboard if the chat opens empty."
              : "Opening " + provider.label + ". If the chat opens empty, use <strong>Copy prompt</strong> below.",
              "ok");
          } else {
            say(copied
              ? "Prompt copied. Paste it into " + provider.label + " and press send — " +
                provider.label + " cannot accept a prompt through a link."
              : "Open " + provider.label + ", then use <strong>Copy prompt</strong> below and paste it in.",
              copied ? "ok" : "warn");
          }
        });
      });
    });

    var copyBtn = root.querySelector("[data-copy-prompt]");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        KI.copy(prompt).then(function (ok) {
          if (ok) {
            say("Prompt copied. Paste it into a new chat and press send.", "ok");
          } else {
            var reveal = root.querySelector(".prompt-reveal");
            if (reveal) reveal.open = true;
            say("Copy was blocked by the browser. Select the prompt text below and copy it manually.", "warn");
          }
        });
      });
    }

    var resetBtn = root.querySelector("[data-reset-note]");
    if (resetBtn) {
      resetBtn.addEventListener("click", function () { say(defaultNote, null); });
    }
  });
})();
