/* Knowledge InSight — vetting feedback links.
 *
 * In-progress programs ask readers to report what they find. A report is far
 * more useful when it names the exact item, and far less likely to be sent if
 * the reader has to describe where they were. So the link is prefilled.
 *
 * Three values go into the form:
 *
 *   loc    the stable location id, c1.m1.l2.i7 — not a title, because titles
 *          get edited and the id is what stays sortable in the sheet
 *   where  a human-readable location, for reading the responses at a glance
 *   page   the full URL including the item anchor, to jump straight back
 *
 * To connect a Google Form: open it, choose Send > Get pre-filled link, put
 * placeholder text in the three location fields, and copy the resulting URL.
 * The entry ids look like `entry.1234567890`. Put the bare form URL and the
 * three ids into content/site.json. Any id left blank is simply skipped, and
 * the link still works.
 */
(function () {
  "use strict";

  var KI = window.KI;
  if (!KI) return;

  var links = KI.$$("[data-feedback-link]");
  if (!links.length) return;

  var heading = KI.$("h1");
  var pageTitle = heading ? heading.textContent.trim() : document.title;

  links.forEach(function (link) {
    var base = link.getAttribute("href");
    if (!base || base === "#") return;

    var loc = link.getAttribute("data-loc") || "";
    var where = link.getAttribute("data-where") || pageTitle;

    // An item link should return the reader to the item, not the page top.
    var item = link.closest("[data-item-id]");
    var anchor = item && item.id ? "#" + item.id : "";
    var pageUrl = location.origin + location.pathname + anchor;

    var params = [];
    add(params, link.getAttribute("data-field-loc"), loc);
    add(params, link.getAttribute("data-field-where"), where);
    add(params, link.getAttribute("data-field-page"), pageUrl);
    if (!params.length) return;

    params.unshift("usp=pp_url");
    link.href = base + (base.indexOf("?") === -1 ? "?" : "&") + params.join("&");
  });

  function add(list, field, value) {
    if (!field || !value) return;
    list.push(encodeURIComponent(field) + "=" + encodeURIComponent(value));
  }
})();
