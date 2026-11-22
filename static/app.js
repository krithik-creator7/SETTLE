/**
 * Settle — frontend.
 *
 * No build step, no framework: a small amount of vanilla JS driving the
 * REST API in app/routes/api.py. State for the active group lives in
 * `state` below and is re-fetched from the server after every mutation,
 * so the UI can never drift from what's actually persisted.
 */
(() => {
  "use strict";

  const CURRENCIES = window.SETTLE_CURRENCIES || {};

  const state = {
    group: null,       // { id, name, currency, participants: [names] }
    participants: [],  // staged names before the group is created
  };

  // ---------------------------------------------------------------- dom --
  const $ = (id) => document.getElementById(id);

  const setupScreen = $("setup-screen");
  const dashboardScreen = $("dashboard-screen");

  // ------------------------------------------------------------- toast --
  let toastTimer = null;
  function toast(message, isError = false) {
    const el = $("toast");
    el.textContent = message;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 3000);
  }

  // --------------------------------------------------------------- api --
  async function api(path, options = {}) {
    const res = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.error || `Request failed (${res.status})`);
    }
    return body;
  }

  function currencySymbol() {
    const c = CURRENCIES[state.group?.currency];
    return c ? c.symbol : "";
  }
  function money(amount) {
    return `${currencySymbol()}${Number(amount).toFixed(2)}`;
  }

  // ======================================================= setup screen =
  function renderParticipantChips() {
    const list = $("participants-list");
    list.innerHTML = "";
    state.participants.forEach((name, i) => {
      const chip = document.createElement("div");
      chip.className = "chip";
      chip.innerHTML = `<span>${escapeHtml(name)}</span>`;
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "×";
      removeBtn.onclick = () => {
        state.participants.splice(i, 1);
        renderParticipantChips();
      };
      chip.appendChild(removeBtn);
      list.appendChild(chip);
    });
  }

  function addParticipantFromInput() {
    const input = $("participant-input");
    const name = input.value.trim();
    if (!name) return;
    if (state.participants.includes(name)) {
      toast("That name is already in the group", true);
      return;
    }
    state.participants.push(name);
    input.value = "";
    renderParticipantChips();
  }

  $("add-participant-btn").addEventListener("click", addParticipantFromInput);
  $("participant-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addParticipantFromInput();
    }
  });

  $("setup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const groupName = $("group-name").value.trim();
    const currency = $("group-currency").value;

    if (!groupName) return toast("Give the group a name", true);
    if (state.participants.length < 2) {
      return toast("Add at least two participants", true);
    }

    try {
      const group = await api("/groups", {
        method: "POST",
        body: JSON.stringify({
          groupName,
          currency,
          participants: state.participants,
        }),
      });
      state.group = group;
      enterDashboard();
    } catch (err) {
      toast(err.message, true);
    }
  });

  // ===================================================== dashboard screen =
  function enterDashboard() {
    setupScreen.classList.add("hidden");
    dashboardScreen.classList.remove("hidden");

    $("dashboard-group-name").textContent = state.group.name;
    $("dashboard-participants").textContent = state.group.participants.join(" · ");

    populateExpenseFormOptions();
    refreshExpenses();
    refreshBalancesAndSettlements();
  }

  $("new-group-btn").addEventListener("click", () => {
    if (!confirm("Start a new group? This won't delete the old one, you just won't be looking at it.")) return;
    state.group = null;
    state.participants = [];
    $("group-name").value = "";
    renderParticipantChips();
    dashboardScreen.classList.add("hidden");
    setupScreen.classList.remove("hidden");
  });

  // Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // ---- expense form options ----
  function populateExpenseFormOptions() {
    const paidBySelect = $("expense-paid-by");
    paidBySelect.innerHTML = state.group.participants
      .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
      .join("");

    const splitList = $("split-among-list");
    splitList.innerHTML = state.group.participants
      .map((name) => `
        <label class="checkbox-row">
          <input type="checkbox" class="split-checkbox" value="${escapeHtml(name)}" checked />
          <span>${escapeHtml(name)}</span>
        </label>
      `).join("");

    splitList.querySelectorAll(".split-checkbox").forEach((cb) => {
      cb.addEventListener("change", renderContributionInputs);
    });
    renderContributionInputs();
  }

  function selectedSplitNames() {
    return Array.from(document.querySelectorAll(".split-checkbox:checked")).map((cb) => cb.value);
  }

  function renderContributionInputs() {
    const container = $("contributions-list");
    const names = selectedSplitNames();
    container.innerHTML = names.map((name) => `
      <div class="contribution-row">
        <span>${escapeHtml(name)}</span>
        <input type="number" class="contribution-input" data-name="${escapeHtml(name)}"
               step="0.01" min="0" placeholder="0.00" />
      </div>
    `).join("");
  }

  $("expense-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const description = $("expense-description").value.trim();
    const amount = parseFloat($("expense-amount").value);
    const paidBy = $("expense-paid-by").value;
    const splitAmong = selectedSplitNames();

    if (!description) return toast("Add a description", true);
    if (!amount || amount <= 0) return toast("Enter a valid amount", true);
    if (splitAmong.length === 0) return toast("Pick at least one person to split with", true);

    const contributors = {};
    document.querySelectorAll(".contribution-input").forEach((input) => {
      const value = parseFloat(input.value);
      if (value > 0) contributors[input.dataset.name] = value;
    });

    try {
      await api(`/groups/${state.group.id}/expenses`, {
        method: "POST",
        body: JSON.stringify({ description, amount, paidBy, splitAmong, contributors }),
      });
      e.target.reset();
      populateExpenseFormOptions();
      refreshExpenses();
      refreshBalancesAndSettlements();
      toast("Expense added");
    } catch (err) {
      toast(err.message, true);
    }
  });

  async function refreshExpenses() {
    const expenses = await api(`/groups/${state.group.id}/expenses`);
    const list = $("expense-list");

    if (expenses.length === 0) {
      list.innerHTML = `<p class="empty-state">No expenses yet. Add the first one above.</p>`;
      return;
    }

    list.innerHTML = expenses.slice().reverse().map((exp) => `
      <div class="expense-item" data-id="${exp.id}">
        <div>
          <div>${escapeHtml(exp.description)}</div>
          <div class="meta">
            ${escapeHtml(exp.paidBy)} paid · split ${exp.splitAmong.length} ways
            ${Object.keys(exp.contributors).length ? "· has direct contributions" : ""}
          </div>
        </div>
        <div style="display:flex;align-items:center;">
          <span class="amount">${money(exp.amount)}</span>
          <button class="delete-btn" title="Delete expense">✕</button>
        </div>
      </div>
    `).join("");

    list.querySelectorAll(".expense-item").forEach((row) => {
      row.querySelector(".delete-btn").addEventListener("click", async () => {
        try {
          await api(`/groups/${state.group.id}/expenses/${row.dataset.id}`, { method: "DELETE" });
          refreshExpenses();
          refreshBalancesAndSettlements();
        } catch (err) {
          toast(err.message, true);
        }
      });
    });
  }

  async function refreshBalancesAndSettlements() {
    const data = await api(`/groups/${state.group.id}/settlements`);

    const balancesList = $("balances-list");
    const entries = Object.entries(data.balances);
    balancesList.innerHTML = entries.length === 0
      ? `<p class="empty-state">Nothing to show yet.</p>`
      : entries.map(([name, amount]) => `
          <div class="balance-row">
            <span>${escapeHtml(name)}</span>
            <span class="${amount >= 0 ? "positive" : "negative"}">
              ${amount >= 0 ? "is owed " : "owes "}${money(Math.abs(amount))}
            </span>
          </div>
        `).join("");

    const settlementsList = $("settlements-list");
    settlementsList.innerHTML = data.settlements.length === 0
      ? `<p class="empty-state">Everyone's settled up 🎉</p>`
      : data.settlements.map((s) => `
          <div class="settlement-row">
            <span>${escapeHtml(s.from)}</span>
            <span class="arrow">→</span>
            <span>${escapeHtml(s.to)}</span>
            <strong style="margin-left:auto;">${money(s.amount)}</strong>
          </div>
        `).join("");
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  renderParticipantChips();
})();
