(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function fetchCredentials() {
    return "same-origin";
  }

  function handleUnauthorized() {
    window.location.href = "/";
  }

  function apiGet(url) {
    return fetch(url, {
      credentials: fetchCredentials(),
      headers: { Accept: "application/json" },
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) handleUnauthorized();
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function apiSend(method, url, body) {
    return fetch(url, {
      method: method,
      credentials: fetchCredentials(),
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) handleUnauthorized();
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function setMessage(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.classList.remove("is-error", "is-ok");
    if (kind === "error") el.classList.add("is-error");
    if (kind === "ok") el.classList.add("is-ok");
  }

  function showElement(el, visible) {
    if (!el) return;
    if (visible) {
      el.classList.remove("is-hidden");
      el.removeAttribute("hidden");
    } else {
      el.classList.add("is-hidden");
      el.setAttribute("hidden", "");
    }
  }

  // ---- Role banner + switcher (v2 §9.2) ----

  var currentEffectiveRole = null;
  var allRoles = [];

  function populateRoleSelect(selected) {
    var select = $("role-banner-select");
    if (!select) return;
    select.innerHTML = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Choose a role…";
    select.appendChild(placeholder);
    allRoles.forEach(function (role) {
      var opt = document.createElement("option");
      opt.value = role;
      opt.textContent = role;
      if (role === selected) opt.selected = true;
      select.appendChild(opt);
    });
  }

  function renderRoleBanner(data) {
    allRoles = data.roles || [];
    currentEffectiveRole = data.effective_role || null;
    var currentEl = $("role-banner-current");
    if (currentEl) currentEl.textContent = currentEffectiveRole || "Not set";
    populateRoleSelect(currentEffectiveRole);

    var prompt = $("role-picker-prompt");
    showElement(prompt, !currentEffectiveRole);
  }

  function loadRole() {
    return apiGet("/api/trap-drills/role").then(function (r) {
      if (!r.ok) {
        setMessage($("td-message"), (r.data && r.data.error) || "Could not load role.", "error");
        return;
      }
      renderRoleBanner(r.data);
    });
  }

  function wireRoleBanner() {
    var select = $("role-banner-select");
    if (select) {
      select.addEventListener("change", function () {
        var role = select.value;
        if (!role) return;
        apiSend("PUT", "/api/trap-drills/role", { role: role }).then(function (r) {
          if (!r.ok) {
            setMessage($("td-message"), (r.data && r.data.error) || "Could not save role.", "error");
            return;
          }
          renderRoleBanner(r.data);
          setMessage($("td-message"), "Role set to " + role + ".", "ok");
          loadDueQueue();
          loadDashboard();
        });
      });
    }

    var switchAppBtn = $("btn-switch-app-trapdrills");
    if (switchAppBtn) {
      switchAppBtn.addEventListener("click", function () {
        window.location.href = "/";
      });
    }

    var signOutBtn = $("btn-sign-out-trapdrills");
    if (signOutBtn) {
      signOutBtn.addEventListener("click", function () {
        apiSend("POST", "/api/users/logout", {}).finally(function () {
          window.location.href = "/";
        });
      });
    }
  }

  // ---- Tabs (Today's Review / Dashboard / Manage / History) ----

  function wireTabs() {
    var tabs = document.querySelectorAll(".trap-drills-nav .tab");
    var panels = {
      review: $("td-panel-review"),
      dashboard: $("td-panel-dashboard"),
      manage: $("td-panel-manage"),
      history: $("td-panel-history"),
    };
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) {
          t.classList.remove("is-active");
          t.setAttribute("aria-selected", "false");
        });
        tab.classList.add("is-active");
        tab.setAttribute("aria-selected", "true");

        var target = tab.getAttribute("data-td-tab");
        Object.keys(panels).forEach(function (key) {
          showElement(panels[key], key === target);
        });

        if (target === "review") loadDueQueue();
        if (target === "dashboard") loadDashboard();
        if (target === "manage") loadManageQuestions();
        if (target === "history") loadHistory();
      });
    });
  }

  // ---- Category Dashboard (v2 §9.4) ----

  function renderDashboard(categories) {
    var table = $("dashboard-table");
    var tbody = $("dashboard-table-body");
    var emptyState = $("dashboard-empty-state");
    if (!tbody) return;
    tbody.textContent = "";

    if (!categories || !categories.length) {
      showElement(table, false);
      showElement(emptyState, true);
      return;
    }

    showElement(emptyState, false);
    showElement(table, true);

    categories.forEach(function (row) {
      var tr = document.createElement("tr");

      function addCell(text) {
        var td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      }

      addCell(row.category || "—");
      addCell(String(row.total_questions != null ? row.total_questions : 0));
      addCell(String(row.attempted_count != null ? row.attempted_count : 0));
      addCell(String(row.mastered_count != null ? row.mastered_count : 0));
      addCell((row.accuracy_percent != null ? row.accuracy_percent : 0) + "%");

      var flagTd = document.createElement("td");
      if (row.is_weak) {
        var badge = document.createElement("span");
        badge.className = "weak-category-badge";
        badge.textContent = "Needs work";
        flagTd.appendChild(badge);
      }
      tr.appendChild(flagTd);

      tbody.appendChild(tr);
    });
  }

  function loadDashboard() {
    return apiGet("/api/trap-drills/stats").then(function (r) {
      if (!r.ok) {
        setMessage($("td-message"), (r.data && r.data.error) || "Could not load dashboard.", "error");
        return;
      }
      renderDashboard(r.data.categories || []);
    });
  }

  // ---- Today's Review (v2 §9.3) ----

  var dueQueue = [];
  var sessionTotal = 0;
  var answeredCount = 0;

  function updateProgressIndicator() {
    var el = $("review-progress");
    if (!el) return;
    if (sessionTotal === 0) {
      el.textContent = "";
      return;
    }
    el.textContent = answeredCount + " of " + sessionTotal + " today";
  }

  function showEmptyState() {
    showElement($("review-question-card"), false);
    showElement($("review-empty-state"), true);
    updateProgressIndicator();
  }

  function renderCurrentQuestion() {
    if (!dueQueue.length) {
      showEmptyState();
      return;
    }
    var item = dueQueue[0];
    showElement($("review-empty-state"), false);
    showElement($("review-question-card"), true);
    $("review-category").textContent = item.category || "";
    $("review-prompt").textContent = item.prompt || "";
    $("review-answer-input").value = "";
    showElement($("review-self-assess"), true);
    showElement($("review-reveal"), false);
    // Personalized (ai_personalized) questions get a "Report this question"
    // action (v2 §7.3, wired for real in Module 11).
    showElement($("btn-report-question"), !!item.is_personalized);
    updateProgressIndicator();
  }

  function loadDueQueue() {
    return apiGet("/api/trap-drills/questions/due?limit=15").then(function (r) {
      if (!r.ok) {
        setMessage($("td-message"), (r.data && r.data.error) || "Could not load due questions.", "error");
        return;
      }
      currentEffectiveRole = r.data.effective_role || null;
      if (!currentEffectiveRole) {
        showElement($("review-question-card"), false);
        showElement($("review-empty-state"), false);
        $("review-progress").textContent = "";
        return;
      }
      dueQueue = r.data.questions || [];
      sessionTotal = dueQueue.length;
      answeredCount = 0;
      renderCurrentQuestion();
    });
  }

  function submitAnswer(wasCorrect) {
    if (!dueQueue.length) return;
    var item = dueQueue[0];
    var btnCorrect = $("btn-review-correct");
    var btnIncorrect = $("btn-review-incorrect");
    if (btnCorrect) btnCorrect.disabled = true;
    if (btnIncorrect) btnIncorrect.disabled = true;

    apiSend("POST", "/api/trap-drills/questions/answer", {
      question_id: item.question_id,
      was_correct: wasCorrect,
    })
      .then(function (r) {
        if (!r.ok) {
          setMessage($("td-message"), (r.data && r.data.error) || "Could not submit answer.", "error");
          return;
        }
        $("reveal-trap").textContent = r.data.trap_answer || "";
        $("reveal-correct").textContent = r.data.correct_answer || "";
        $("reveal-explanation").textContent = r.data.explanation || "";
        showElement($("review-self-assess"), false);
        showElement($("review-reveal"), true);
      })
      .finally(function () {
        if (btnCorrect) btnCorrect.disabled = false;
        if (btnIncorrect) btnIncorrect.disabled = false;
      });
  }

  function wireReview() {
    var correctBtn = $("btn-review-correct");
    if (correctBtn) correctBtn.addEventListener("click", function () { submitAnswer(true); });

    var incorrectBtn = $("btn-review-incorrect");
    if (incorrectBtn) incorrectBtn.addEventListener("click", function () { submitAnswer(false); });

    var nextBtn = $("btn-review-next");
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        dueQueue.shift();
        answeredCount += 1;
        renderCurrentQuestion();
      });
    }

    var reportBtn = $("btn-report-question");
    if (reportBtn) {
      reportBtn.addEventListener("click", function () {
        if (!dueQueue.length) return;
        var item = dueQueue[0];
        apiSend("POST", "/api/trap-drills/questions/" + encodeURIComponent(item.question_id) + "/report", {}).then(
          function (r) {
            if (!r.ok) {
              setMessage($("td-message"), (r.data && r.data.error) || "Could not report question.", "error");
              return;
            }
            setMessage($("td-message"), "Question reported and removed from your due queue.", "ok");
            dueQueue.shift();
            answeredCount += 1;
            renderCurrentQuestion();
          }
        );
      });
    }
  }

  // ---- Question management (v2 §9.5, Module 7) ----

  var editingQuestionId = null;

  function populateManageRoleSelects() {
    var formRoleSelect = $("question-form-role");
    var filterSelect = $("question-list-role-filter");
    [formRoleSelect, filterSelect].forEach(function (select) {
      if (!select) return;
      var previousValue = select.value;
      select.innerHTML = "";
      allRoles.forEach(function (role) {
        var opt = document.createElement("option");
        opt.value = role;
        opt.textContent = role;
        select.appendChild(opt);
      });
      if (previousValue && allRoles.indexOf(previousValue) !== -1) {
        select.value = previousValue;
      } else if (currentEffectiveRole && allRoles.indexOf(currentEffectiveRole) !== -1) {
        select.value = currentEffectiveRole;
      }
    });
  }

  function populateCategoryDatalistFromQuestions(questions) {
    var datalist = $("question-form-category-options");
    if (!datalist) return;
    datalist.innerHTML = "";
    var seen = {};
    (questions || []).forEach(function (q) {
      var cat = (q.category || "").trim();
      if (!cat || seen[cat]) return;
      seen[cat] = true;
      var opt = document.createElement("option");
      opt.value = cat;
      datalist.appendChild(opt);
    });
  }

  function startEditQuestion(q) {
    editingQuestionId = q.question_id;
    $("question-form-id").value = q.question_id;
    $("question-form-mode").textContent = "Editing question";
    $("btn-question-form-submit").textContent = "Save changes";
    showElement($("btn-question-form-cancel"), true);
    $("question-form-role").value = q.role;
    $("question-form-category").value = q.category;
    $("question-form-prompt").value = q.prompt;
    $("question-form-trap-answer").value = q.trap_answer;
    $("question-form-correct-answer").value = q.correct_answer;
    $("question-form-explanation").value = q.explanation;
  }

  function resetQuestionForm() {
    editingQuestionId = null;
    $("question-form-id").value = "";
    $("question-form-mode").textContent = "Add a new question";
    $("btn-question-form-submit").textContent = "Add question";
    showElement($("btn-question-form-cancel"), false);
    var form = $("form-question");
    if (form) form.reset();
    var filterSelect = $("question-list-role-filter");
    var formRoleSelect = $("question-form-role");
    if (filterSelect && formRoleSelect && filterSelect.value) {
      formRoleSelect.value = filterSelect.value;
    }
  }

  function deleteQuestion(questionId) {
    apiSend("DELETE", "/api/trap-drills/questions/" + encodeURIComponent(questionId), {}).then(function (r) {
      if (!r.ok) {
        setMessage($("question-form-message"), (r.data && r.data.error) || "Could not delete question.", "error");
        return;
      }
      setMessage($("question-form-message"), "Question deleted.", "ok");
      loadQuestionList();
    });
  }

  function renderQuestionList(questions) {
    var table = $("question-list-table");
    var tbody = $("question-list-table-body");
    var emptyState = $("question-list-empty-state");
    if (!tbody) return;
    tbody.textContent = "";

    if (!questions || !questions.length) {
      showElement(table, false);
      showElement(emptyState, true);
      return;
    }
    showElement(emptyState, false);
    showElement(table, true);

    questions.forEach(function (q) {
      var tr = document.createElement("tr");

      function addCell(text) {
        var td = document.createElement("td");
        td.textContent = text || "";
        tr.appendChild(td);
      }

      addCell(q.category);
      addCell(q.prompt);
      addCell(q.review_status);

      var actionsTd = document.createElement("td");
      var editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn link";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", function () {
        startEditQuestion(q);
      });
      actionsTd.appendChild(editBtn);

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn link danger-link";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", function () {
        deleteQuestion(q.question_id);
      });
      actionsTd.appendChild(deleteBtn);

      tr.appendChild(actionsTd);
      tbody.appendChild(tr);
    });
  }

  function loadQuestionList() {
    var filterSelect = $("question-list-role-filter");
    var role = filterSelect ? filterSelect.value : "";
    if (!role) return Promise.resolve();
    return apiGet("/api/trap-drills/questions?role=" + encodeURIComponent(role)).then(function (r) {
      if (!r.ok) {
        setMessage($("question-form-message"), (r.data && r.data.error) || "Could not load questions.", "error");
        return;
      }
      renderQuestionList(r.data.questions || []);
      populateCategoryDatalistFromQuestions(r.data.questions || []);
    });
  }

  function reviewQuestion(questionId, decision) {
    apiSend("POST", "/api/trap-drills/questions/" + encodeURIComponent(questionId) + "/review", {
      decision: decision,
    }).then(function (r) {
      if (!r.ok) {
        setMessage($("question-form-message"), (r.data && r.data.error) || "Could not review question.", "error");
        return;
      }
      setMessage($("question-form-message"), "Question " + r.data.review_status + ".", "ok");
      loadPendingReview();
      loadQuestionList();
    });
  }

  function renderPendingReview(questions) {
    var table = $("pending-review-table");
    var tbody = $("pending-review-table-body");
    var emptyState = $("pending-review-empty-state");
    if (!tbody) return;
    tbody.textContent = "";

    if (!questions || !questions.length) {
      showElement(table, false);
      showElement(emptyState, true);
      return;
    }
    showElement(emptyState, false);
    showElement(table, true);

    questions.forEach(function (q) {
      var tr = document.createElement("tr");
      [q.role, q.category, q.prompt].forEach(function (text) {
        var td = document.createElement("td");
        td.textContent = text || "";
        tr.appendChild(td);
      });

      var actionsTd = document.createElement("td");
      var approveBtn = document.createElement("button");
      approveBtn.type = "button";
      approveBtn.className = "btn primary";
      approveBtn.textContent = "Approve";
      approveBtn.addEventListener("click", function () {
        reviewQuestion(q.question_id, "approve");
      });
      actionsTd.appendChild(approveBtn);

      var rejectBtn = document.createElement("button");
      rejectBtn.type = "button";
      rejectBtn.className = "btn secondary";
      rejectBtn.textContent = "Reject";
      rejectBtn.addEventListener("click", function () {
        reviewQuestion(q.question_id, "reject");
      });
      actionsTd.appendChild(rejectBtn);

      tr.appendChild(actionsTd);
      tbody.appendChild(tr);
    });
  }

  function loadPendingReview() {
    return apiGet("/api/trap-drills/questions/pending-review").then(function (r) {
      if (!r.ok) {
        setMessage($("question-form-message"), (r.data && r.data.error) || "Could not load pending review.", "error");
        return;
      }
      renderPendingReview(r.data.questions || []);
    });
  }

  function loadManageQuestions() {
    populateManageRoleSelects();
    loadQuestionList();
    loadPendingReview();
  }

  function wireQuestionManagement() {
    var form = $("form-question");
    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var msg = $("question-form-message");
        setMessage(msg, "", "");

        var fields = {
          role: $("question-form-role").value,
          category: $("question-form-category").value.trim(),
          prompt: $("question-form-prompt").value.trim(),
          trap_answer: $("question-form-trap-answer").value.trim(),
          correct_answer: $("question-form-correct-answer").value.trim(),
          explanation: $("question-form-explanation").value.trim(),
        };

        var req = editingQuestionId
          ? apiSend("PUT", "/api/trap-drills/questions/" + encodeURIComponent(editingQuestionId), fields)
          : apiSend("POST", "/api/trap-drills/questions", fields);

        req.then(function (r) {
          if (!r.ok) {
            setMessage(msg, (r.data && r.data.error) || "Could not save question.", "error");
            return;
          }
          setMessage(msg, editingQuestionId ? "Question updated." : "Question added.", "ok");
          resetQuestionForm();
          loadQuestionList();
        });
      });
    }

    var cancelBtn = $("btn-question-form-cancel");
    if (cancelBtn) cancelBtn.addEventListener("click", resetQuestionForm);

    var filterSelect = $("question-list-role-filter");
    if (filterSelect) filterSelect.addEventListener("change", loadQuestionList);
  }

  // ---- History (v2 §9.6, Module 8) ----

  var historyPage = 1;
  var historyPageSize = 10;
  var historyTotalPages = 1;

  function populateHistoryRoleFilter() {
    var select = $("history-role-filter");
    if (!select) return;
    var previousValue = select.value;
    select.innerHTML = "";
    var allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = "All roles";
    select.appendChild(allOpt);
    allRoles.forEach(function (role) {
      var opt = document.createElement("option");
      opt.value = role;
      opt.textContent = role;
      select.appendChild(opt);
    });
    select.value = previousValue || "";
  }

  function renderHistory(data) {
    var table = $("history-table");
    var tbody = $("history-table-body");
    var emptyState = $("history-empty-state");
    if (!tbody) return;
    tbody.textContent = "";

    var items = data.items || [];
    if (!items.length) {
      showElement(table, false);
      showElement(emptyState, true);
    } else {
      showElement(emptyState, false);
      showElement(table, true);

      items.forEach(function (item) {
        var tr = document.createElement("tr");

        function addCell(text) {
          var td = document.createElement("td");
          td.textContent = text;
          tr.appendChild(td);
        }

        addCell(item.prompt || "");
        addCell(item.role || "");
        addCell(item.was_correct ? "Correct" : "Incorrect");
        addCell(String(item.box_after != null ? item.box_after : ""));
        addCell(item.answered_at ? new Date(item.answered_at).toLocaleString() : "");

        tbody.appendChild(tr);
      });
    }

    historyTotalPages = data.total_pages || 1;
    var indicator = $("history-page-indicator");
    if (indicator) indicator.textContent = "Page " + data.page + " of " + historyTotalPages;

    var prevBtn = $("btn-history-prev");
    var nextBtn = $("btn-history-next");
    if (prevBtn) prevBtn.disabled = data.page <= 1;
    if (nextBtn) nextBtn.disabled = data.page >= historyTotalPages;
  }

  function loadHistory() {
    populateHistoryRoleFilter();
    var roleFilter = $("history-role-filter");
    var role = roleFilter ? roleFilter.value : "";
    var url =
      "/api/trap-drills/history?page=" + historyPage + "&page_size=" + historyPageSize +
      (role ? "&role=" + encodeURIComponent(role) : "");
    return apiGet(url).then(function (r) {
      if (!r.ok) {
        setMessage($("td-message"), (r.data && r.data.error) || "Could not load history.", "error");
        return;
      }
      renderHistory(r.data);
    });
  }

  function wireHistory() {
    var prevBtn = $("btn-history-prev");
    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        if (historyPage > 1) {
          historyPage -= 1;
          loadHistory();
        }
      });
    }

    var nextBtn = $("btn-history-next");
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        if (historyPage < historyTotalPages) {
          historyPage += 1;
          loadHistory();
        }
      });
    }

    var roleFilter = $("history-role-filter");
    if (roleFilter) {
      roleFilter.addEventListener("change", function () {
        historyPage = 1;
        loadHistory();
      });
    }
  }

  function boot() {
    wireRoleBanner();
    wireTabs();
    wireReview();
    wireQuestionManagement();
    wireHistory();
    loadRole().then(loadDueQueue);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
