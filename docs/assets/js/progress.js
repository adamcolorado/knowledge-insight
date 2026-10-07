/* Knowledge InSight — progress.
 *
 * Progress is a flat map of item id -> timestamp in this browser's local
 * storage. There are no accounts and nothing is sent anywhere. Rollups for a
 * lesson, a course, or the whole program are computed by counting ids under a
 * prefix, so no server and no second data structure is needed.
 *
 *   item    c1.m1.l1.i7
 *   lesson  c1.m1.l1
 *   project c1.project
 *   course  c1
 */
(function () {
  "use strict";

  var KI = window.KI;
  if (!KI) return;

  var state = KI.store.read(KI.keys.progress, {}) || {};

  function save() { KI.store.write(KI.keys.progress, state); }

  function isDone(id) { return Object.prototype.hasOwnProperty.call(state, id); }

  function setDone(id, done) {
    if (done) state[id] = Date.now();
    else delete state[id];
    save();
    refresh();
  }

  /* Count completed items under a prefix. The trailing dot keeps l1 from
     matching l10. */
  function countUnder(prefix) {
    var exact = prefix + ".";
    var total = 0;
    for (var key in state) {
      if (key === prefix || key.indexOf(exact) === 0) total++;
    }
    return total;
  }

  function pct(done, total) {
    if (!total) return 0;
    return Math.max(0, Math.min(100, Math.round((done / total) * 100)));
  }

  /* ------------------------------------------------------------- painting */

  function refresh() {
    KI.$$("[data-done-for]").forEach(function (btn) {
      var done = isDone(btn.getAttribute("data-done-for"));
      btn.setAttribute("aria-pressed", String(done));
      var label = btn.querySelector(".done-label");
      if (label) label.textContent = done ? "Done" : "Mark done";
      var item = btn.closest(".item");
      if (item) item.classList.toggle("is-done", done);
    });

    KI.$$("[data-progress-for]").forEach(function (dot) {
      var total = parseInt(dot.getAttribute("data-item-count"), 10) || 0;
      var done = countUnder(dot.getAttribute("data-progress-for"));
      var value = pct(done, total);
      dot.setAttribute("data-state", value >= 100 ? "done" : value > 0 ? "some" : "none");
      dot.style.setProperty("--pct", value + "%");
      dot.setAttribute("aria-label", done + " of " + total + " items complete");
    });

    KI.$$("[data-progress-bar-for]").forEach(function (bar) {
      var total = parseInt(bar.getAttribute("data-item-count"), 10) || 0;
      var value = pct(countUnder(bar.getAttribute("data-progress-bar-for")), total);
      bar.style.width = value + "%";
    });

    KI.$$("[data-progress-text-for]").forEach(function (el) {
      var total = parseInt(el.getAttribute("data-item-count"), 10) || 0;
      var value = pct(countUnder(el.getAttribute("data-progress-text-for")), total);
      el.textContent = value + "%";
    });

    KI.$$("[data-rail-for]").forEach(function (link) {
      link.closest(".rail-row").classList.toggle("is-done", isDone(link.getAttribute("data-rail-for")));
    });
  }

  /* --------------------------------------------------------------- wiring */

  KI.$$("[data-done-for]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-done-for");
      setDone(id, !isDone(id));
    });
  });

  // A second tab marking something done should update this one.
  window.addEventListener("storage", function (e) {
    if (e.key !== KI.keys.progress) return;
    state = KI.store.read(KI.keys.progress, {}) || {};
    refresh();
  });

  KI.progress = {
    isDone: isDone,
    setDone: setDone,
    countUnder: countUnder,
    refresh: refresh,
    reset: function () { state = {}; save(); refresh(); }
  };

  refresh();
})();
