/* Knowledge InSight — the sticky lesson navigation bar.
 *
 * Replaces the two sidebars. It tracks which item is in view, steps between
 * items, and drives the breadcrumb and item dropdowns.
 *
 * "Which item am I on" is deliberately not "the first item intersecting the
 * viewport": items are long, so at any moment several are partly visible. The
 * current item is the last one whose top has passed under the sticky bar,
 * which is what a reader means by where they are.
 */
(function () {
  "use strict";

  var KI = window.KI;
  if (!KI) return;

  var bar = KI.$("#learnbar");
  if (!bar) return;

  /* ---------------------------------------------------------- dropdowns */

  var pickers = KI.$$(".lb-pick", bar);

  function closeAll(except) {
    pickers.forEach(function (pick) {
      if (pick === except) return;
      var btn = pick.querySelector(".lb-pick-btn");
      var menu = pick.querySelector(".lb-menu");
      if (btn) btn.setAttribute("aria-expanded", "false");
      if (menu) menu.hidden = true;
      pick.classList.remove("is-open");
    });
  }

  pickers.forEach(function (pick) {
    var btn = pick.querySelector(".lb-pick-btn");
    var menu = pick.querySelector(".lb-menu");
    if (!btn || !menu) return;

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = menu.hidden;
      closeAll(pick);
      menu.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      pick.classList.toggle("is-open", open);
      if (open) {
        var current = menu.querySelector("a.is-current") || menu.querySelector("a");
        if (current) current.scrollIntoView({ block: "nearest" });
      }
    });
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".lb-pick")) closeAll();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var open = bar.querySelector(".lb-pick.is-open");
    if (!open) return;
    closeAll();
    var btn = open.querySelector(".lb-pick-btn");
    if (btn) btn.focus();
  });

  /* --------------------------------------------------------- item steps */

  var items = KI.$$(".item");
  if (!items.length) return;

  var current = KI.$("[data-item-current]", bar);
  var stepBtns = KI.$$("[data-item-step]", bar);
  var jumps = KI.$$("[data-item-jump]", bar);
  var index = 0;

  function barHeight() {
    return bar.getBoundingClientRect().height + 8;
  }

  function scrollToItem(n) {
    var target = items[Math.max(0, Math.min(items.length - 1, n))];
    if (!target) return;
    var top = window.pageYOffset + target.getBoundingClientRect().top - barHeight();
    window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }

  function paint() {
    if (current) current.textContent = String(index + 1);
    stepBtns.forEach(function (btn) {
      var delta = parseInt(btn.getAttribute("data-item-step"), 10);
      btn.disabled = delta < 0 ? index <= 0 : index >= items.length - 1;
    });
    jumps.forEach(function (link, n) {
      link.classList.toggle("is-current", n === index);
    });
  }

  stepBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      scrollToItem(index + parseInt(btn.getAttribute("data-item-step"), 10));
    });
  });

  jumps.forEach(function (link, n) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      closeAll();
      scrollToItem(n);
    });
  });

  /* The last item whose top has passed under the bar is the one you are on. */
  function recompute() {
    var line = barHeight() + 4;
    var found = 0;
    for (var i = 0; i < items.length; i++) {
      if (items[i].getBoundingClientRect().top <= line) found = i;
      else break;
    }
    if (found !== index) {
      index = found;
      paint();
    }
  }

  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () {
      recompute();
      ticking = false;
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);

  // Deep links (#item-7) land before the first scroll event fires.
  window.addEventListener("hashchange", function () { window.setTimeout(recompute, 50); });

  paint();
  recompute();
})();
