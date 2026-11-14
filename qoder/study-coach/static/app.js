"use strict";

// StudyRecall frontend. All persistent application state lives in the real
// PowerContext Server; localStorage is used ONLY to remember which space was last
// selected in this browser tab (a navigation convenience, never the data itself).
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const LS_SPACE = "studyrecall.selected_scope";

let currentScope = localStorage.getItem(LS_SPACE) || "";

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(msg, kind = "ok") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 3600);
}

function showError(message) {
  const b = $("#error-banner");
  b.textContent = "⚠ " + message;
  b.classList.remove("hidden");
}
function clearError() { $("#error-banner").classList.add("hidden"); }

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok) {
    let msg = data && data.error ? data.error : `请求失败 (HTTP ${res.status})`;
    if (res.status === 422) {
      const det = data && data.detail ? data.detail : null;
      msg = "输入不合法：" + (Array.isArray(det) ? det.map((d) => (d.loc || []).slice(1).join(".") + " " + d.msg).join("；") : JSON.stringify(det));
    }
    throw new Error(msg);
  }
  return data;
}

function setBadge(state, text) {
  const el = $("#backend-badge");
  el.className = `badge badge-${state}`;
  el.textContent = text;
}

async function checkHealth() {
  try {
    const h = await api("/api/health");
    setBadge("ok", `● PowerContext 已连接`);
    return h;
  } catch (e) {
    setBadge("err", "● 后端不可用");
    showError("无法连接 PowerContext 后端：" + e.message);
    return null;
  }
}

function scopePath(suffix = "") {
  return `/api/spaces/${encodeURIComponent(currentScope)}${suffix}`;
}

function requireSpace() {
  if (!currentScope) { toast("请先选择或新建学习空间", "err"); return false; }
  return true;
}

// ---------- spaces ----------
async function loadSpaces() {
  try {
    const spaces = await api("/api/spaces");
    const sel = $("#space-select");
    sel.innerHTML = "";
    if (!spaces.length) {
      const o = document.createElement("option");
      o.value = ""; o.textContent = "（暂无空间，请新建或载入示例）";
      sel.appendChild(o);
      currentScope = ""; localStorage.removeItem(LS_SPACE);
      refreshSide();
      return;
    }
    for (const s of spaces) {
      const o = document.createElement("option");
      o.value = s.scope_id;
      o.textContent = s.title;
      sel.appendChild(o);
    }
    if (!spaces.some((s) => s.scope_id === currentScope)) {
      currentScope = spaces[0].scope_id;
    }
    sel.value = currentScope;
    localStorage.setItem(LS_SPACE, currentScope);
    refreshSide();
  } catch (e) {
    showError(e.message);
  }
}

function refreshSide() {
  const has = !!currentScope;
  $("#preference-form").classList.toggle("hidden", !has);
  $("#no-space").classList.toggle("hidden", has);
  if (!has) return;
  loadPreference();
  showActiveView();
}

// ---------- preference ----------
async function loadPreference() {
  if (!requireSpace()) return;
  try {
    const { preference } = await api(scopePath("/preference"));
    $("#pref-minutes").value = preference ? preference.daily_minutes : 25;
    $("#pref-focus").value = preference ? preference.focus : "";
  } catch (e) { showError(e.message); }
}

async function savePreference() {
  if (!requireSpace()) return;
  clearError();
  try {
    await api(scopePath("/preference"), { method: "PUT", body: {
      daily_minutes: parseInt($("#pref-minutes").value, 10),
      focus: $("#pref-focus").value.trim(),
    }});
    toast("学习偏好已保存到 PowerContext");
  } catch (e) { showError(e.message); toast("保存失败", "err"); }
}

// ---------- notes ----------
async function loadNotes() {
  if (!requireSpace()) return;
  clearError();
  try {
    const notes = await api(scopePath("/notes"));
    const box = $("#notes-list");
    if (!notes.length) { box.innerHTML = `<div class="empty-note">还没有笔记。导入笔记后，其知识点将进入复习计划。</div>`; return; }
    box.innerHTML = notes.map((n) => {
      const kps = (n.note.knowledge_points || []).map((k) => `<span class="chip">${esc(k)}</span>`).join("");
      return `<div class="item">
        <h4>${esc(n.note.title)}</h4>
        <div class="meta">来源：${esc(n.note.origin)} · ${esc(n.note.created_at)}</div>
        <div style="margin:6px 0">${esc(n.note.body)}</div>
        <div>${kps}</div>
        <div class="cite">PowerContext Source · ${esc(n.source_id)} · ${esc(n.content_digest)}</div>
      </div>`;
    }).join("");
  } catch (e) { showError(e.message); }
}

async function addNote(evt) {
  evt.preventDefault();
  if (!requireSpace()) return;
  clearError();
  const points = $("#note-points").value.split(/[，,]/).map((s) => s.trim()).filter(Boolean);
  try {
    await api(scopePath("/notes"), { method: "POST", body: {
      title: $("#note-title").value.trim(),
      body: $("#note-body").value.trim(),
      origin: $("#note-origin").value.trim(),
      knowledge_points: points,
    }});
    $("#note-form").reset();
    toast("笔记已写入 PowerContext Source");
    loadNotes();
  } catch (e) { showError(e.message); toast("导入失败", "err"); }
}

// ---------- weak points ----------
async function loadWeak() {
  if (!requireSpace()) return;
  clearError();
  try {
    const items = await api(scopePath("/weak-points"));
    const box = $("#weak-list");
    if (!items.length) { box.innerHTML = `<div class="empty-note">尚未标记薄弱知识点。</div>`; return; }
    box.innerHTML = items.map((w) => `<div class="item">
      <div class="plan-head"><h4>${esc(w.topic)}</h4><span class="chip ${w.severity >= 4 ? "err" : "warn"}">薄弱程度 ${w.severity}/5</span></div>
      <div class="meta">${esc(w.note || "")} · 更新于 ${esc(w.updated_at)}</div>
    </div>`).join("");
  } catch (e) { showError(e.message); }
}

async function addWeak(evt) {
  evt.preventDefault();
  if (!requireSpace()) return;
  clearError();
  try {
    await api(scopePath("/weak-points"), { method: "POST", body: {
      topic: $("#weak-topic").value.trim(),
      severity: parseInt($("#weak-severity").value, 10),
    }});
    $("#weak-topic").value = "";
    toast("薄弱点已保存");
    loadWeak();
  } catch (e) { showError(e.message); toast("保存失败", "err"); }
}

// ---------- reviews ----------
async function loadReviews() {
  if (!requireSpace()) return;
  clearError();
  try {
    const items = await api(scopePath("/reviews"));
    const box = $("#reviews-list");
    if (!items.length) { box.innerHTML = `<div class="empty-note">还没有复习记录。记录后，计划会反映变化。</div>`; return; }
    const label = { fail: "未掌握", partial: "部分掌握", mastered: "已掌握" };
    const chip = { fail: "err", partial: "warn", mastered: "ok" };
    box.innerHTML = items.slice().reverse().map((r) => `<div class="item">
      <div class="plan-head"><h4>${esc(r.topic)}</h4><span class="chip ${chip[r.result]}">${label[r.result] || esc(r.result)}${r.score != null ? " · " + r.score + "/5" : ""}</span></div>
      <div class="meta">${esc(r.note || "")} · ${esc(r.reviewed_at)}</div>
    </div>`).join("");
  } catch (e) { showError(e.message); }
}

async function addReview(evt) {
  evt.preventDefault();
  if (!requireSpace()) return;
  clearError();
  const score = $("#review-score").value;
  try {
    await api(scopePath("/reviews"), { method: "POST", body: {
      topic: $("#review-topic").value.trim(),
      result: $("#review-result").value,
      score: score === "" ? null : parseInt(score, 10),
      note: $("#review-note").value.trim(),
    }});
    $("#review-note").value = "";
    toast("复习结果已记录到 PowerContext Memory");
    loadReviews();
  } catch (e) { showError(e.message); toast("记录失败", "err"); }
}

// ---------- plan ----------
async function genPlan() {
  if (!requireSpace()) return;
  clearError();
  try {
    const p = await api(scopePath("/plan"), { method: "POST", body: {} });
    $("#plan-summary").innerHTML = p.items.length
      ? `共 ${p.total_topics} 个知识点，本次安排 <b>${p.items.length}</b> 项，合计 <b>${p.planned_minutes}</b> 分钟（预算 ${p.daily_minutes} 分钟/天）。`
      : `当前无需复习的知识点（共 ${p.total_topics} 个）。${(p.notes || []).join(" ")}`;
    const box = $("#plan-list");
    if (!p.items.length) { box.innerHTML = `<div class="empty-note">导入笔记或标记薄弱点后，这里会生成复习计划。</div>`; return; }
    box.innerHTML = p.items.map((it) => {
      const reasons = it.reasons.map((r) => `<li>${esc(r)}</li>`).join("");
      const factors = it.factors.map((f) => `<div class="factor"><b>${esc(f.name)}</b><span>${esc(f.detail)}</span></div>`).join("");
      const cites = (it.related_note_sources || []).map((s) => `<span class="cite">笔记 ${esc(s)}</span>`).join(" ");
      const resLabel = it.last_result ? { fail: "上次未掌握", partial: "上次部分掌握", mastered: "上次已掌握" }[it.last_result] : "尚未复习";
      return `<div class="item plan-item ${it.overdue ? "due" : ""}">
        <div class="plan-head">
          <h4>${esc(it.topic)}</h4>
          <span class="plan-mins">${it.allocated_minutes} 分钟 · 下次间隔 ${it.next_interval_days} 天 · 优先级 ${it.priority_score}</span>
        </div>
        <div class="meta">${esc(resLabel)}${it.days_since_last_review != null ? " · 距今 " + it.days_since_last_review + " 天" : ""}</div>
        <ul class="reasons">${reasons}</ul>
        <div class="factors">${factors}</div>
        ${cites ? `<div style="margin-top:6px">${cites}</div>` : ""}
      </div>`;
    }).join("");
  } catch (e) { showError(e.message); toast("生成失败", "err"); }
}

// ---------- search ----------
async function doSearch(evt) {
  evt.preventDefault();
  if (!requireSpace()) return;
  clearError();
  const q = $("#search-q").value.trim();
  if (!q) { toast("请输入关键词", "err"); return; }
  try {
    const r = await api(scopePath("/search") + "?q=" + encodeURIComponent(q));
    const box = $("#search-list");
    let html = "";
    for (const h of r.memory_hits) {
      html += `<div class="item"><div class="meta">Memory 命中（${h.matched_by.join(",")} · 分数 ${h.score.toFixed(3)}）</div><div>${esc(h.text)}</div></div>`;
    }
    for (const h of r.note_hits) {
      html += `<div class="item"><h4>${esc(h.title)}</h4><div>${esc(h.snippet)}…</div>
        <div class="cite">来源引用 · scope ${esc(h.source_citation.scope_id)} · ${esc(h.source_citation.source_id)} · ${esc(h.source_citation.content_digest)}</div></div>`;
    }
    box.innerHTML = html || `<div class="empty-note">未检索到与“${esc(q)}”相关的记忆。</div>`;
  } catch (e) { showError(e.message); toast("检索失败", "err"); }
}

// ---------- views ----------
const VIEW_LOADERS = { plan: genPlan, notes: loadNotes, weak: loadWeak, reviews: loadReviews, search: () => { $("#search-list").innerHTML = ""; } };
let activeView = "plan";
function showActiveView() {
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-" + activeView).classList.remove("hidden");
  if (currentScope && VIEW_LOADERS[activeView]) VIEW_LOADERS[activeView]();
}

// ---------- new-space modal ----------
function openModal() { $("#modal").classList.remove("hidden"); $("#space-title").focus(); }
function closeModal() { $("#modal").classList.add("hidden"); }
async function createSpace() {
  const title = $("#space-title").value.trim();
  if (!title) { toast("请输入空间标题", "err"); return; }
  try {
    const s = await api("/api/spaces", { method: "POST", body: { title, summary: $("#space-summary").value.trim() } });
    currentScope = s.scope_id; localStorage.setItem(LS_SPACE, currentScope);
    closeModal(); $("#space-title").value = ""; $("#space-summary").value = "";
    toast("学习空间（PowerContext Scope）已创建");
    await loadSpaces();
  } catch (e) { showError(e.message); toast("创建失败", "err"); }
}

async function seedSample() {
  clearError();
  try {
    const r = await api("/api/seed-sample", { method: "POST" });
    currentScope = r.space.scope_id; localStorage.setItem(LS_SPACE, currentScope);
    toast("已载入合成示例（内容为演示用虚构资料）");
    await loadSpaces();
    activeView = "plan"; $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === "plan"));
    showActiveView();
  } catch (e) { showError(e.message); toast("载入失败", "err"); }
}

function wire() {
  $("#reload-spaces").addEventListener("click", loadSpaces);
  $("#space-select").addEventListener("change", (e) => { currentScope = e.target.value; localStorage.setItem(LS_SPACE, currentScope); refreshSide(); });
  $("#new-space").addEventListener("click", openModal);
  $("#seed-sample").addEventListener("click", seedSample);
  $("#save-preference").addEventListener("click", savePreference);
  $("#note-form").addEventListener("submit", addNote);
  $("#weak-form").addEventListener("submit", addWeak);
  $("#review-form").addEventListener("submit", addReview);
  $("#gen-plan").addEventListener("click", genPlan);
  $("#search-form").addEventListener("submit", doSearch);
  $("#modal-cancel").addEventListener("click", closeModal);
  $("#modal-ok").addEventListener("click", createSpace);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  $$(".tab").forEach((t) => t.addEventListener("click", () => {
    activeView = t.dataset.view;
    $$(".tab").forEach((x) => x.classList.toggle("active", x === t));
    showActiveView();
  }));
}

async function init() {
  wire();
  await checkHealth();
  await loadSpaces();
}
document.addEventListener("DOMContentLoaded", init);
