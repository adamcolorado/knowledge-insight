/* Knowledge InSight — shared behaviour.
 *
 * Everything here is progressive: the pages are fully readable with this file
 * blocked. It adds the mobile menu, the clipboard helper, the print-one-item
 * control, and the "pick up where you left off" link.
 */
(function () {
  "use strict";

  var KI = (window.KI = window.KI || {});

  /* ---------------------------------------------------------------- store */

  KI.store = {
    read: function (key, fallback) {
      try {
        var raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (e) {
        return fallback;
      }
    },
    write: function (key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (e) {
        return false;   // private mode, or storage disabled
      }
    }
  };

  KI.keys = {
    progress: "ki.progress.v1",
    quiz: "ki.quiz.v1",
    last: "ki.last.v1",
    ui: "ki.ui.v1"
  };

  KI.$ = function (sel, scope) { return (scope || document).querySelector(sel); };
  KI.$$ = function (sel, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(sel));
  };

  /* ------------------------------------------------------------ main menu */

  var navToggle = KI.$(".nav-toggle");
  var siteNav = KI.$("#site-nav");
  if (navToggle && siteNav) {
    navToggle.addEventListener("click", function () {
      var open = siteNav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  /* --------------------------------------------------------- resume point */

  // The resume point is kept per program, so a second program does not
  // overwrite where you were in the first.
  var programId = document.body.getAttribute("data-program") || "default";
  var isLearning = /page-(lesson|module|course)/.test(document.body.className);

  if (isLearning) {
    var heading = KI.$("h1");
    var eyebrow = KI.$(".lesson-head .eyebrow, .course-head .eyebrow");
    var last = KI.store.read(KI.keys.last, {});
    last[programId] = {
      href: location.pathname,
      title: heading ? heading.textContent.trim() : document.title,
      label: eyebrow ? eyebrow.textContent.trim() : "",
      at: Date.now()
    };
    KI.store.write(KI.keys.last, last);
  }

  KI.$$("[data-resume-for]").forEach(function (link) {
    var saved = KI.store.read(KI.keys.last, {})[programId];
    if (!saved || !saved.href || saved.href === location.pathname) return;
    link.href = saved.href;
    var label = KI.$("span:not(.ico)", link) || link;
    label.textContent = "Resume: " + saved.title;
    link.setAttribute("title", "Pick up where you left off");
  });

  /* ------------------------------------------- print / copy a single item */

  KI.$$("[data-print-item]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var item = btn.closest(".item");
      if (!item) return;
      item.classList.add("print-target");
      document.body.classList.add("printing-one");
      window.print();
      window.setTimeout(function () {
        item.classList.remove("print-target");
        document.body.classList.remove("printing-one");
      }, 500);
    });
  });

  KI.$$("[data-copy-item]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var item = btn.closest(".item");
      var prose = item && KI.$(".prose", item);
      if (!prose) return;
      var title = KI.$(".item-title", item);
      var text = (title ? title.textContent.trim() + "\n\n" : "") + prose.innerText.trim();
      KI.copy(text).then(function (ok) {
        var label = KI.$("span:not(.ico)", btn);
        if (!label) return;
        var original = label.textContent;
        label.textContent = ok ? "Copied" : "Copy failed";
        window.setTimeout(function () { label.textContent = original; }, 2000);
      });
    });
  });

  /* ------------------------------------------------------------ clipboard */

  KI.copy = function (text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; },
                                                      function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  };

  /* The fallback matters more than it looks: navigator.clipboard only exists
     in a secure context, so over plain http on a phone (local network testing,
     for instance) this is the only path. iOS ignores .select() on a readonly
     textarea and ignores elements positioned off-screen, hence the Range plus
     setSelectionRange, and the 1px visible-but-transparent box at 16px, which
     is the size Safari will not zoom to. */
  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText =
      "position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;" +
      "outline:0;opacity:0;font-size:16px";
    document.body.appendChild(area);

    var selection = document.getSelection();
    var previous = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

    var ok = false;
    try {
      area.contentEditable = "true";
      area.readOnly = false;
      if (selection) {
        var range = document.createRange();
        range.selectNodeContents(area);
        selection.removeAllRanges();
        selection.addRange(range);
      }
      area.setSelectionRange(0, text.length);
      ok = document.execCommand("copy");
    } catch (e) {
      ok = false;
    }

    document.body.removeChild(area);
    if (previous && selection) {
      selection.removeAllRanges();
      selection.addRange(previous);
    }
    return ok;
  }
})();
