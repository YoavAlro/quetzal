"use strict";

const api = {
  services: () => fetch("/api/services").then((r) => r.json()),
  questions: (s) => fetch(`/api/services/${s}/questions`).then((r) => r.json()),
  create: (s, body) => send(`/api/services/${s}/questions`, "POST", body),
  update: (s, id, body) => send(`/api/services/${s}/questions/${id}`, "PUT", body),
  remove: (s, id) => fetch(`/api/services/${s}/questions/${id}`, { method: "DELETE" }).then((r) => r.json()),
  sessions: () => fetch("/api/sessions").then((r) => r.json()),
  session: (id) => fetch(`/api/sessions/${id}`).then((r) => r.json()),
  history: () => fetch("/api/history").then((r) => r.json()),
};

async function send(url, method, body) {
  const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return r.json();
}

const state = { services: [], current: null, questions: [], editing: null };

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const $ = (id) => document.getElementById(id);

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}

/* ---------------- Tabs ---------------- */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    tab.classList.add("active");
    $(`view-${tab.dataset.view}`).classList.add("active");
    if (tab.dataset.view === "history") loadHistory();
  });
});

/* ---------------- Questions ---------------- */
async function loadServices() {
  state.services = await api.services();
  const list = $("svc-list");
  list.innerHTML = "";
  state.services.forEach((svc) => {
    const btn = document.createElement("button");
    btn.className = "svc" + (state.current === svc.name ? " active" : "");
    btn.innerHTML = `<span class="name">${esc(svc.name)}</span>
      <span class="count">${svc.reviewed}/${svc.total} reviewed</span>`;
    btn.onclick = () => selectService(svc.name);
    list.appendChild(btn);
  });
  if (!state.current && state.services.length) selectService(state.services[0].name);
}

async function selectService(name) {
  state.current = name;
  document.querySelectorAll(".svc").forEach((b) =>
    b.classList.toggle("active", b.querySelector(".name").textContent === name)
  );
  const svc = state.services.find((s) => s.name === name);
  $("svc-title").textContent = name;
  $("svc-roots").textContent = svc ? svc.code_roots.join("  ·  ") : "";
  state.questions = await api.questions(name);
  renderTable();
}

function renderTable() {
  const wrap = $("q-table");
  if (!state.questions.length) {
    wrap.innerHTML = `<div class="empty">No questions yet. Click “Add question”.</div>`;
    return;
  }
  const rows = state.questions
    .map(
      (q) => `<tr class="row">
      <td style="width:46%">
        <div class="q-text">${esc(q.question)}</div>
        <div class="q-id">${esc(q.id)}</div>
        <div style="margin-top:6px">${q.tags.map((t) => `<span class="chip tag">${esc(t)}</span>`).join("")}</div>
      </td>
      <td><span class="chip ${esc(q.difficulty)}">${esc(q.difficulty)}</span></td>
      <td><div class="gt">${esc(q.ground_truth)}</div></td>
      <td>${toggleHtml(q)}</td>
      <td class="cell-actions">
        <button class="btn btn-sm" data-edit="${esc(q.id)}">Edit</button>
        <button class="btn btn-sm btn-danger" data-del="${esc(q.id)}">Delete</button>
      </td>
    </tr>`
    )
    .join("");
  wrap.innerHTML = `<table>
    <thead><tr><th>Question</th><th>Difficulty</th><th>Ground truth</th><th>Reviewed</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>`;

  wrap.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => openModal(b.dataset.edit)));
  wrap.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => removeQuestion(b.dataset.del)));
  wrap.querySelectorAll("[data-toggle]").forEach((b) => (b.onclick = () => toggleReviewed(b.dataset.toggle)));
}

const toggleHtml = (q) =>
  `<span class="toggle ${q.reviewed ? "on" : ""}" data-toggle="${esc(q.id)}">
     <span class="track"></span>${q.reviewed ? '<span class="badge-reviewed">yes</span>' : '<span class="badge-pending">pending</span>'}
   </span>`;

async function toggleReviewed(id) {
  const q = state.questions.find((x) => x.id === id);
  await api.update(state.current, id, { ...q, reviewed: !q.reviewed });
  q.reviewed = !q.reviewed;
  renderTable();
  loadServices();
  toast(q.reviewed ? "Marked reviewed" : "Marked pending");
}

async function removeQuestion(id) {
  if (!confirm(`Delete question “${id}”?`)) return;
  await api.remove(state.current, id);
  state.questions = state.questions.filter((q) => q.id !== id);
  renderTable();
  loadServices();
  toast("Question deleted");
}

/* ---------------- Modal ---------------- */
function openModal(id) {
  const q = id ? state.questions.find((x) => x.id === id) : null;
  state.editing = q;
  $("modal-title").textContent = q ? "Edit question" : "New question";
  $("f-question").value = q ? q.question : "";
  $("f-gt").value = q ? q.ground_truth : "";
  $("f-difficulty").value = q ? q.difficulty : "medium";
  $("f-tags").value = q ? q.tags.join(", ") : "";
  $("f-id").value = q ? q.id : "";
  $("f-id").disabled = !!q;
  setToggle($("f-reviewed-toggle"), q ? q.reviewed : false);
  $("modal-bg").classList.add("show");
}
function closeModal() { $("modal-bg").classList.remove("show"); }

function setToggle(elm, on) { elm.classList.toggle("on", on); elm.dataset.on = on ? "1" : "0"; }
$("f-reviewed-toggle").onclick = () => setToggle($("f-reviewed-toggle"), $("f-reviewed-toggle").dataset.on !== "1");
$("modal-close").onclick = closeModal;
$("modal-cancel").onclick = closeModal;
$("add-btn").onclick = () => openModal(null);
$("modal-bg").onclick = (e) => { if (e.target === $("modal-bg")) closeModal(); };

$("modal-save").onclick = async () => {
  const body = {
    question: $("f-question").value.trim(),
    ground_truth: $("f-gt").value.trim(),
    difficulty: $("f-difficulty").value,
    tags: $("f-tags").value.split(",").map((t) => t.trim()).filter(Boolean),
    reviewed: $("f-reviewed-toggle").dataset.on === "1",
    id: $("f-id").value.trim() || null,
  };
  if (!body.question || !body.ground_truth) { toast("Question and ground truth are required"); return; }
  try {
    if (state.editing) await api.update(state.current, state.editing.id, body);
    else await api.create(state.current, body);
    closeModal();
    state.questions = await api.questions(state.current);
    renderTable();
    loadServices();
    toast("Saved");
  } catch (e) { toast(e.message); }
};

/* ---------------- History ---------------- */
let historyCache = null;

async function loadHistory() {
  const sessions = await api.sessions();
  $("sessions-meta").textContent = sessions.length ? `${sessions.length} run(s)` : "";
  const wrap = $("sessions");
  if (!sessions.length) {
    wrap.innerHTML = `<div class="empty">No runs yet. Run the benchmark, then refresh.</div>`;
    $("trend-chart").innerHTML = "";
    return;
  }
  wrap.innerHTML = sessions
    .map((s) => {
      const o = s.overall || {};
      const cost = o.total_cost_usd != null ? ` · $${o.total_cost_usd}` : "";
      return `<div class="panel scard" data-session="${esc(s.session_id)}">
        <div class="sid">${esc(s.session_id)}</div>
        <div class="big">${o.accuracy_pct ?? 0}%</div>
        <div class="meta">${o.correct ?? 0}/${o.judged ?? 0} correct · ${fmt(o.avg_tokens)} avg tok${cost}</div>
        <span class="model">${esc(s.agent_client || "?")} · ${esc(s.agent_model)}</span>
      </div>`;
    })
    .join("");
  wrap.querySelectorAll("[data-session]").forEach((c) => (c.onclick = () => showSession(c.dataset.session)));

  historyCache = await api.history();
  const sel = $("trend-service");
  const names = Object.keys(historyCache.per_service).sort();
  sel.innerHTML = `<option value="__overall__">All suites (overall)</option>` +
    names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
  sel.onchange = renderTrend;
  $("trend-metric").onchange = renderTrend;
  renderTrend();
}

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());

function renderTrend() {
  if (!historyCache) return;
  const svc = $("trend-service").value;
  const metric = $("trend-metric").value;
  const series = svc === "__overall__" ? historyCache.overall : historyCache.per_service[svc] || [];
  $("trend-chart").innerHTML = lineChart(series, metric);
}

function lineChart(series, metric) {
  if (!series.length) return `<div class="empty">No data for this selection.</div>`;
  const W = 900, H = 280, pad = { l: 48, r: 16, t: 16, b: 44 };
  const xs = series.map((_, i) => i);
  const ys = series.map((p) => p[metric] ?? 0);
  const isPct = metric === "accuracy_pct";
  const ymax = isPct ? 100 : Math.max(1, ...ys) * 1.15;
  const px = (i) => pad.l + (xs.length === 1 ? (W - pad.l - pad.r) / 2 : (i / (xs.length - 1)) * (W - pad.l - pad.r));
  const py = (v) => pad.t + (1 - v / ymax) * (H - pad.t - pad.b);

  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((f) => {
      const y = pad.t + f * (H - pad.t - pad.b);
      const val = Math.round(ymax * (1 - f));
      return `<line x1="${pad.l}" y1="${y}" x2="${W - pad.r}" y2="${y}" stroke="#e9edf1" />
        <text x="${pad.l - 8}" y="${y + 4}" text-anchor="end" font-size="11" fill="#68798a">${val}${isPct ? "%" : ""}</text>`;
    })
    .join("");

  const path = ys.map((v, i) => `${i ? "L" : "M"}${px(i)},${py(v)}`).join(" ");
  const area = `${path} L${px(xs.length - 1)},${py(0)} L${px(0)},${py(0)} Z`;
  const dots = ys
    .map((v, i) => `<circle cx="${px(i)}" cy="${py(v)}" r="4" fill="#12a06e"><title>${esc(series[i].session_id)}: ${v}${isPct ? "%" : ""}</title></circle>`)
    .join("");
  const labels = series
    .map((p, i) => (i % Math.ceil(series.length / 8 || 1) === 0
      ? `<text x="${px(i)}" y="${H - pad.b + 18}" text-anchor="middle" font-size="10" fill="#68798a">${esc((p.started_at || "").slice(5, 10))}</text>`
      : ""))
    .join("");

  return `<svg viewBox="0 0 ${W} ${H}" class="chartsvg">
    <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#12a06e" stop-opacity="0.18"/><stop offset="100%" stop-color="#12a06e" stop-opacity="0"/>
    </linearGradient></defs>
    ${grid}
    <path d="${area}" fill="url(#g)" />
    <path d="${path}" fill="none" stroke="#12a06e" stroke-width="2.5" stroke-linejoin="round" />
    ${dots}${labels}
  </svg>
  <div class="legend"><span><i style="background:#12a06e"></i>${isPct ? "Accuracy" : "Avg tokens"} per run (oldest → newest)</span></div>`;
}

async function showSession(id) {
  const report = await api.session(id);
  const rows = report.services
    .map(
      (s) => `<tr class="row"><td>${esc(s.service)}</td>
      <td>${s.correct}/${s.judged}</td>
      <td><span class="chip ${s.accuracy_pct >= 80 ? "easy" : s.accuracy_pct >= 50 ? "medium" : "hard"}">${s.accuracy_pct}%</span></td>
      <td>${s.avg_score}</td><td>${fmt(s.avg_tokens)}</td><td>${fmt(s.total_tokens)}</td><td>${s.total_cost_usd != null ? "$" + s.total_cost_usd : "—"}</td></tr>`
    )
    .join("");
  const oc = report.overall.total_cost_usd != null ? ` · $${report.overall.total_cost_usd}` : "";
  $("session-detail").innerHTML = `<div class="panel panel-pad">
    <div class="chart-head"><h3>Session ${esc(id)}</h3>
      <span class="muted">overall ${report.overall.accuracy_pct}% · ${fmt(report.overall.total_tokens)} tok${oc}</span></div>
    <table><thead><tr><th>Suite</th><th>Correct</th><th>Accuracy</th><th>Avg score</th><th>Avg tok</th><th>Total tok</th><th>Cost</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
  $("session-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

loadServices();
