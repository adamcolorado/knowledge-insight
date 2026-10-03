/* Knowledge InSight — vetting feedback links.
 *
 * In-progress programs ask readers to report what they find. A report is far
 * more useful when it says which page it came from, and far less likely to be
 * sent if the reader has to type that out. So the link is prefilled.
 *
 * To connect a Google Form, open it, choose Send > Get pre-filled link, fill
 * in the two fields with any placeholder text, and copy the resulting URL.
 * The entry ids look like `entry.1234567890`. Put the bare form URL in
 * content/site.json as `feedbackUrl` and the two ids as `feedbackPageField`
 * and `feedbackTitleField`. Leave the ids blank and the link still works, it
 * just arrives empty.
 */
(function () {
  "use strict";

  var KI = window.KI;
  if (!KI) return;

  var links = KI.$$("[data-feedback-link]");
  if (!links.length) return;

  var heading = KI.$("h1");
  var pageTitle = heading ? heading.textContent.trim() : document.title;
  var pageUrl = location.href;

  links.forEach(function (link) {
    var base = link.getAttribute("href");
    if (!base || base === "#") return;

    var params = [];
    var pageField = link.getAttribute("data-field-page");
    var titleField = link.getAttribute("data-field-title");
    if (pageField) params.push(encodeURIComponent(pageField) + "=" + encodeURIComponent(pageUrl));
    if (titleField) params.push(encodeURIComponent(titleField) + "=" + encodeURIComponent(pageTitle));
    if (!params.length) return;

    params.unshift("usp=pp_url");
    link.href = base + (base.indexOf("?") === -1 ? "?" : "&") + params.join("&");
  });
})();
