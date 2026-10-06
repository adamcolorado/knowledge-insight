/* Knowledge InSight — quiz engine.
 *
 * Replaces H5P. The four question types in the source files are:
 *
 *   single     one correct answer, options shuffled
 *   multi      several correct answers, partial credit
 *   text       typed answer, matched case- and punctuation-insensitively
 *              against the accepted answers
 *   dropdowns  one or more <select> blanks inside the sentence
 *
 * Every option carries its own feedback, which is the whole point: a wrong
 * answer should teach something specific. Graded quizzes ship three fixed
 * forms of the same ten questions and rotate them per attempt, so a retake
 * covers the same topics rather than a random draw that might not.
 *
 * Quiz data is fetched on demand, so a lesson page does not carry its quiz
 * until the learner asks for it.
 */
(function () {
  "use strict";

  var KI = window.KI;
  if (!KI) return;

  /* ------------------------------------------------------------- helpers */

  function norm(value) {
    return String(value)
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")   // combining marks left by NFKD
      .replace(/[\u2018\u2019\u02bc]/g, "'")   // curly apostrophes
      .replace(/[^a-z0-9' ]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function shuffled(list) {
    var out = list.slice();
    for (var i = out.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = out[i]; out[i] = out[j]; out[j] = t;
    }
    return out;
  }

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  function quizState() { return KI.store.read(KI.keys.quiz, {}) || {}; }

  function saveQuizState(id, patch) {
    var all = quizState();
    all[id] = Object.assign({}, all[id], patch);
    KI.store.write(KI.keys.quiz, all);
  }

  /* -------------------------------------------------------------- render */

  function renderQuestion(question, index, form) {
    var node = el("section", "q");
    node.setAttribute("data-type", question.type);
    node.setAttribute("role", "group");

    var heading = el("p", "q-num", "Question " + (index + 1));
    heading.id = form.domId + "-q" + index;
    node.setAttribute("aria-labelledby", heading.id);
    node.appendChild(heading);

    var stem = el("div", "q-stem", question.stemHtml);
    node.appendChild(stem);

    if (question.type === "dropdowns") {
      (question.blanks || []).forEach(function (blank) {
        var slot = stem.querySelector('.q-blank[data-blank="' + blank.n + '"]');
        if (!slot) {
          slot = el("span", "q-blank");
          slot.setAttribute("data-blank", String(blank.n));
          stem.appendChild(slot);
        }
        var select = el("select");
        select.setAttribute("aria-label", "Blank " + blank.n);
        select.appendChild(new Option("Choose…", ""));
        shuffled(blank.options).forEach(function (option) {
          select.appendChild(new Option(option.text, option.id));
        });
        slot.appendChild(select);
      });
      node.appendChild(el("p", "q-fb", ""));
      node.querySelector(".q-fb").hidden = true;
      return node;
    }

    if (question.type === "text") {
      node.appendChild(el("p", "q-hint", "Type your answer. Capitalisation and punctuation do not matter."));
      var input = el("input", "q-text-input");
      input.type = "text";
      input.autocomplete = "off";
      input.setAttribute("aria-labelledby", heading.id);
      node.appendChild(input);
      var feedback = el("p", "q-fb", "");
      feedback.hidden = true;
      node.appendChild(feedback);
      return node;
    }

    var multi = question.type === "multi";
    if (multi) node.appendChild(el("p", "q-hint", "Select all that apply."));

    var list = el("ul", "q-options");
    var options = question.shuffle ? shuffled(question.options) : question.options;
    options.forEach(function (option) {
      var li = el("li", "q-option");
      li.setAttribute("data-option", option.id);

      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = multi ? "checkbox" : "radio";
      input.name = form.domId + "-q" + index;
      input.value = option.id;
      label.appendChild(input);
      label.appendChild(el("span", "q-option-text", option.html));
      li.appendChild(label);

      var feedback = el("p", "q-fb", option.feedbackHtml || "");
      feedback.hidden = true;
      li.appendChild(feedback);
      list.appendChild(li);
    });
    node.appendChild(list);
    return node;
  }

  /* --------------------------------------------------------------- grade */

  function gradeQuestion(question, node) {
    var score = 0;

    if (question.type === "text") {
      var input = node.querySelector(".q-text-input");
      var feedback = node.querySelector(".q-fb");
      var typed = norm(input.value);
      var match = null;
      (question.options || []).forEach(function (option) {
        if (!match && typed && norm(option.text) === typed) match = option;
      });
      input.disabled = true;
      if (match && match.correct) {
        score = 1;
        feedback.className = "q-fb ok";
        feedback.innerHTML = match.feedbackHtml || "Correct.";
        input.classList.add("is-correct");
      } else {
        feedback.className = "q-fb no";
        feedback.innerHTML = (match && match.feedbackHtml) || question.defaultFeedbackHtml ||
          "Not quite.";
        var accepted = (question.options || []).filter(function (o) { return o.correct; })
          .map(function (o) { return o.text; });
        if (accepted.length) {
          feedback.innerHTML += ' <span class="muted">Accepted: ' + accepted.join(" / ") + "</span>";
        }
      }
      feedback.hidden = false;
      return score;
    }

    if (question.type === "dropdowns") {
      var blanks = question.blanks || [];
      var got = 0;
      var notes = [];
      blanks.forEach(function (blank) {
        var slot = node.querySelector('.q-blank[data-blank="' + blank.n + '"]');
        var select = slot && slot.querySelector("select");
        if (!select) return;
        select.disabled = true;
        var chosen = null;
        blank.options.forEach(function (option) {
          if (option.id === select.value) chosen = option;
        });
        var right = !!(chosen && chosen.correct);
        if (right) got++;
        slot.classList.add(right ? "is-correct" : "is-wrong");
        var expected = blank.options.filter(function (o) { return o.correct; })[0];
        notes.push("<strong>Blank " + blank.n + ":</strong> " +
          ((chosen && chosen.feedbackHtml) ||
            (expected ? "The answer is " + expected.text + "." : "")));
      });
      var dropFeedback = node.querySelector(".q-fb");
      dropFeedback.className = "q-fb " + (got === blanks.length ? "ok" : "no");
      dropFeedback.innerHTML = notes.join("<br>");
      dropFeedback.hidden = false;
      return blanks.length ? got / blanks.length : 0;
    }

    var inputs = KI.$$("input", node);
    var correctIds = {};
    var selected = {};
    question.options.forEach(function (o) { if (o.correct) correctIds[o.id] = true; });
    inputs.forEach(function (input) {
      if (input.checked) selected[input.value] = true;
      input.disabled = true;
    });

    var hits = 0, misses = 0, totalCorrect = 0;
    question.options.forEach(function (option) {
      var li = node.querySelector('.q-option[data-option="' + option.id + '"]');
      var feedback = li.querySelector(".q-fb");
      var chosen = !!selected[option.id];
      if (option.correct) totalCorrect++;
      if (chosen && option.correct) { hits++; li.classList.add("is-correct"); }
      else if (chosen && !option.correct) { misses++; li.classList.add("is-wrong"); }
      else if (!chosen && option.correct) { li.classList.add("is-missed"); }
      if (chosen || option.correct) {
        feedback.className = "q-fb " + (option.correct ? "ok" : "no");
        feedback.hidden = false;
        if (!chosen && option.correct && !feedback.innerHTML) {
          feedback.innerHTML = "This was one of the correct answers.";
        }
      }
    });

    if (question.type === "multi") {
      // Partial credit, with wrong picks cancelling right ones.
      score = totalCorrect ? Math.max(0, (hits - misses) / totalCorrect) : 0;
    } else {
      score = hits > 0 && misses === 0 ? 1 : 0;
    }
    return score;
  }

  /* ----------------------------------------------------------- the panel */

  function buildPanel(root, data) {
    var id = root.getAttribute("data-quiz-id");
    var kind = root.getAttribute("data-quiz-kind");
    var graded = kind === "graded-quiz";
    var mount = root.querySelector("[data-quiz-mount]");
    var saved = quizState()[id] || {};
    var attempts = saved.attempts || 0;
    var formIndex = data.forms.length > 1 ? attempts % data.forms.length : 0;
    var questions = data.forms[formIndex];

    var form = { domId: "q-" + id.replace(/\./g, "-") + "-" + attempts };
    mount.innerHTML = "";
    mount.hidden = false;

    if (data.forms.length > 1) {
      mount.appendChild(el("p", "quiz-form-note",
        "Form " + (formIndex + 1) + " of " + data.forms.length +
        ". Each form covers the same ten topics; retaking rotates to the next one."));
    }

    var nodes = questions.map(function (question, index) {
      var node = renderQuestion(question, index, form);
      mount.appendChild(node);
      return node;
    });

    var controls = el("div", "quiz-controls");
    var submit = el("button", "btn btn-primary");
    submit.type = "button";
    submit.textContent = graded ? "Submit answers" : "Check my answers";
    var reset = el("button", "btn");
    reset.type = "button";
    reset.textContent = "Start over";
    reset.hidden = true;
    var close = el("button", "btn btn-quiet");
    close.type = "button";
    close.textContent = "Close";
    controls.appendChild(submit);
    controls.appendChild(reset);
    controls.appendChild(close);
    mount.appendChild(controls);

    var result = el("div", "quiz-result");
    result.hidden = true;
    result.setAttribute("role", "status");
    mount.appendChild(result);

    submit.addEventListener("click", function () {
      var total = 0;
      questions.forEach(function (question, index) {
        total += gradeQuestion(question, nodes[index]);
      });
      var percent = Math.round((total / questions.length) * 100);

      submit.hidden = true;
      reset.hidden = false;
      result.hidden = false;

      var best = Math.max(saved.best || 0, percent);
      saveQuizState(id, { best: best, last: percent, attempts: attempts + 1, at: Date.now() });

      var headline = el("p", "quiz-score", percent + "%");
      result.innerHTML = "";
      result.appendChild(headline);

      if (graded) {
        var passed = percent >= (data.passPercent || 80);
        result.className = "quiz-result " + (passed ? "is-pass" : "is-fail");
        result.appendChild(el("p", null, passed
          ? "That is at or above the " + data.passPercent + "% target. Read the feedback on anything you missed, then move on."
          : "The target is " + data.passPercent + "%. Read the feedback below, review the module, and take the quiz again — the next attempt uses a different form of the same questions."));
      } else {
        result.className = "quiz-result";
        result.appendChild(el("p", null,
          "This check is not graded and nothing is recorded beyond this browser. Read the feedback on anything you missed and retry as often as you like."));
      }
      if (best > percent) {
        result.appendChild(el("p", "muted", "Your best on this quiz so far: " + best + "%."));
      }
      paintBest(root, id);
      result.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });

    reset.addEventListener("click", function () { buildPanel(root, data); });

    close.addEventListener("click", function () {
      mount.hidden = true;
      mount.innerHTML = "";
      var starter = root.querySelector("[data-quiz-start]");
      starter.hidden = false;
      starter.focus();
    });

    root.querySelector("[data-quiz-start]").hidden = true;
  }

  function paintBest(root, id) {
    var badge = root.querySelector("[data-quiz-best]");
    if (!badge) return;
    var saved = quizState()[id];
    if (!saved || typeof saved.best !== "number") { badge.hidden = true; return; }
    badge.hidden = false;
    badge.textContent = "Best so far: " + saved.best + "% (" +
      saved.attempts + (saved.attempts === 1 ? " attempt)" : " attempts)");
  }

  /* --------------------------------------------------------------- wiring */

  KI.$$("[data-quiz]").forEach(function (root) {
    var id = root.getAttribute("data-quiz-id");
    var cache = null;
    paintBest(root, id);

    root.querySelector("[data-quiz-start]").addEventListener("click", function (e) {
      var button = e.currentTarget;
      if (cache) { buildPanel(root, cache); return; }

      button.disabled = true;
      var label = button.querySelector("span:not(.ico)");
      var original = label ? label.textContent : "";
      if (label) label.textContent = "Loading…";

      fetch(root.getAttribute("data-quiz-src"))
        .then(function (response) {
          if (!response.ok) throw new Error(response.status + " " + response.statusText);
          return response.json();
        })
        .then(function (data) {
          cache = data;
          button.disabled = false;
          if (label) label.textContent = original;
          buildPanel(root, data);
        })
        .catch(function (error) {
          button.disabled = false;
          if (label) label.textContent = original;
          var mount = root.querySelector("[data-quiz-mount]");
          mount.hidden = false;
          mount.innerHTML = '<p class="q-fb no">This quiz could not be loaded (' +
            String(error.message).replace(/[<>&]/g, "") +
            "). Check your connection and reload the page to try again.</p>";
        });
    });
  });
})();
