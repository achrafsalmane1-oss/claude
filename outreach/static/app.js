/* Local outreach MVP - vanilla JS SPA */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CHANNELS = { email: "Email", linkedin: "LinkedIn", call: "Call" };

const api = {
  async req(method, url, body) {
    const r = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => ({ error: "bad response" }));
    if (data && data.error && method !== "GET") toast(data.error, true);
    return data;
  },
  get: (u) => api.req("GET", u),
  post: (u, b) => api.req("POST", u, b || {}),
  del: (u) => api.req("DELETE", u),
};

function toast(msg, bad) {
  const el = document.createElement("div");
  el.className = "toast" + (bad ? " bad" : "");
  el.textContent = msg;
  $("#toast-root").appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

function modal({ title, body, footer, wide }) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="backdrop"><div class="modal" ${wide ? 'style="width:min(1050px,100%)"' : ""}>
    <header><strong>${esc(title)}</strong><button class="x" data-close>&times;</button></header>
    <div class="bd">${body}</div>${footer ? `<footer>${footer}</footer>` : ""}</div></div>`;
  root.querySelector(".backdrop").addEventListener("click", (e) => {
    if (e.target.classList.contains("backdrop") || e.target.dataset.close !== undefined) closeModal();
  });
  return root.querySelector(".modal");
}
const closeModal = () => ($("#modal-root").innerHTML = "");

const initials = (c) => ((c.first_name || "")[0] || "") + ((c.last_name || "")[0] || "") || "?";
const fullName = (c) => [c.first_name, c.last_name].filter(Boolean).join(" ") || c.email || c.phone || "Unknown";
const when = (iso) => {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + "m ago";
  if (mins < 1440) return Math.round(mins / 60) + "h ago";
  if (mins < 10080) return Math.round(mins / 1440) + "d ago";
  return d.toLocaleDateString();
};
const statusTag = (s) => {
  const cls = { replied: "ok", bounced: "bad", unsubscribed: "bad", do_not_contact: "bad", active: "warn" }[s] || "";
  return `<span class="tag ${cls}">${esc(s || "new")}</span>`;
};
const chanTag = (c) => `<span class="tag ${c}">${CHANNELS[c] || c}</span>`;
const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0);

let boot = { counts: {}, settings: {}, lists: [] };
let sel = new Set();

async function refreshBoot() {
  boot = await api.get("/api/bootstrap");
  $("#badge-tasks").textContent = boot.counts.tasks_pending || "";
  $("#badge-inbox").textContent = boot.counts.unread || "";
  $("#badge-campaigns").textContent = boot.counts.campaigns_running || "";
  $("#badge-contacts").textContent = boot.counts.contacts ? String(boot.counts.contacts) : "";
  const dry = boot.settings.dry_run === "1" || !boot.settings.smtp_host;
  const pill = $("#mode-pill");
  pill.textContent = dry ? "DRY RUN" : "LIVE SENDING";
  pill.className = "pill" + (dry ? "" : " live");
  $("#engine-info").textContent = boot.engine && boot.engine.last_tick
    ? "scheduler " + when(boot.engine.last_tick) : "scheduler idle";
}

/* ------------------------------------------------------------------ router */
const views = {};
async function route() {
  const hash = location.hash.replace(/^#\/?/, "") || "dashboard";
  const [name, arg] = hash.split("/");
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === name));
  const main = $("#main");
  main.innerHTML = '<div class="loading">Loading…</div>';
  await refreshBoot();
  try {
    await (views[name] || views.dashboard)(main, arg);
  } catch (e) {
    main.innerHTML = `<div class="empty"><h3>Something broke</h3><p class="muted">${esc(e.message)}</p></div>`;
    console.error(e);
  }
}
window.addEventListener("hashchange", route);

/* --------------------------------------------------------------- dashboard */
views.dashboard = async (el) => {
  const [tasks, campaigns, reports, inbox] = await Promise.all([
    api.get("/api/tasks?status=pending"), api.get("/api/campaigns"),
    api.get("/api/reports?days=30"), api.get("/api/inbox?filter=unread"),
  ]);
  const t = reports.totals;
  const counts = tasks.counts || {};
  el.innerHTML = `
  <div class="head">
    <div><h1>Dashboard</h1><p class="sub">Last 30 days across email, LinkedIn and calls.</p></div>
    <div class="row">
      <button class="btn ghost" id="d-import">Import CSV</button>
      <a class="btn" href="#/tasks">Work the queue</a>
    </div>
  </div>
  <div class="kpis" style="margin-bottom:16px">
    ${kpi(t.contacts, "Contacts", (t.reached || 0) + " touched")}
    ${kpi(t.emails_sent, "Emails sent", pct(t.opens, t.emails_sent) + "% opened")}
    ${kpi(t.linkedin_sent, "LinkedIn sent", "manual queue")}
    ${kpi(t.calls, "Calls logged", (reports.dispositions[0] ? reports.dispositions[0].outcome + " top" : "no calls yet"))}
    ${kpi(t.replies, "Replies", pct(t.replies, t.reached) + "% reply rate")}
    ${kpi(t.bounces + t.unsubscribes, "Bounced / opted out", t.skipped + " steps skipped")}
  </div>
  <div class="grid" style="grid-template-columns:1.2fr 1fr">
    <div class="card pad">
      <div class="spread"><h2>Work waiting on you</h2><a class="sm muted" href="#/tasks">open queue →</a></div>
      <div class="kpis">
        ${kpi(counts.call || 0, "Calls to make", "")}
        ${kpi(counts.linkedin || 0, "LinkedIn actions", "")}
        ${kpi(counts.email || 0, "Manual emails", "")}
      </div>
      ${tasks.rows.length ? `<table style="margin-top:14px"><tbody>${tasks.rows.slice(0, 6).map((r) => `
        <tr><td style="width:34px"><div class="avatar">${esc(initials(r))}</div></td>
        <td><strong>${esc(fullName(r))}</strong><div class="muted xs">${esc(r.company || "")} · ${esc(r.campaign_name || "ad hoc")}</div></td>
        <td style="width:90px">${chanTag(r.channel)}</td></tr>`).join("")}</tbody></table>`
      : '<p class="muted sm" style="margin-top:12px">Nothing queued. Start a campaign to generate tasks.</p>'}
    </div>
    <div class="stack">
      <div class="card pad">
        <div class="spread"><h2>Unread replies</h2><a class="sm muted" href="#/inbox">inbox →</a></div>
        ${inbox.rows.length ? inbox.rows.slice(0, 5).map((r) => `
          <a href="#/inbox/${r.contact_id}" class="li" style="border:0;padding:8px 0">
            <div class="avatar">${esc(initials(r))}</div>
            <div style="min-width:0"><div class="nm">${esc(fullName(r))}</div>
            <div class="mt">${esc(r.snippet || "")}</div></div></a>`).join("")
          : '<p class="muted sm">No unread replies.</p>'}
      </div>
      <div class="card pad">
        <div class="spread"><h2>Campaigns</h2><a class="sm muted" href="#/campaigns">manage →</a></div>
        ${campaigns.length ? campaigns.slice(0, 5).map((c) => `
          <div class="spread" style="padding:6px 0;border-bottom:1px solid var(--line-2)">
            <div><strong class="sm">${esc(c.name)}</strong>
            <div class="muted xs">${c.stats.total} enrolled · ${c.stats.replied || 0} replied</div></div>
            <span class="tag ${c.status === "running" ? "ok" : ""}">${esc(c.status)}</span></div>`).join("")
          : '<p class="muted sm">No campaigns yet. <a href="#/sequences">Build a sequence →</a></p>'}
      </div>
    </div>
  </div>`;
  $("#d-import").onclick = importModal;
};
const kpi = (n, l, d) => `<div class="kpi"><div class="n">${n ?? 0}</div><div class="l">${esc(l)}</div>${d ? `<div class="d">${esc(d)}</div>` : ""}</div>`;

/* ---------------------------------------------------------------- contacts */
let contactFilter = { search: "", status: "", list_id: "", has: "", offset: 0 };

views.contacts = async (el) => {
  const qs = new URLSearchParams(Object.fromEntries(
    Object.entries(contactFilter).filter(([, v]) => v !== "" && v != null)));
  const [data, campaigns] = await Promise.all([
    api.get("/api/contacts?" + qs.toString()), api.get("/api/campaigns")]);
  el.innerHTML = `
  <div class="head">
    <div><h1>Contacts</h1><p class="sub">${data.total} matching · ${boot.counts.contacts} total</p></div>
    <div class="row">
      <a class="btn ghost" href="/api/export?what=contacts&${qs}">Export CSV</a>
      <button class="btn ghost" id="c-new">Add contact</button>
      <button class="btn" id="c-import">Import CSV</button>
    </div>
  </div>
  <div class="card pad" style="margin-bottom:12px">
    <div class="row">
      <input type="text" id="f-search" placeholder="Search name, email, company, phone…" value="${esc(contactFilter.search)}" style="max-width:280px">
      <select id="f-status" style="max-width:150px"><option value="">Any status</option>
        ${["new", "active", "replied", "bounced", "unsubscribed", "do_not_contact", "finished"]
          .map((s) => `<option ${contactFilter.status === s ? "selected" : ""}>${s}</option>`).join("")}</select>
      <select id="f-has" style="max-width:150px"><option value="">Any data</option>
        <option value="email" ${contactFilter.has === "email" ? "selected" : ""}>Has email</option>
        <option value="phone" ${contactFilter.has === "phone" ? "selected" : ""}>Has phone</option>
        <option value="linkedin_url" ${contactFilter.has === "linkedin_url" ? "selected" : ""}>Has LinkedIn</option>
      </select>
      <select id="f-list" style="max-width:180px"><option value="">Any list</option>
        ${boot.lists.map((l) => `<option value="${l.id}" ${String(contactFilter.list_id) === String(l.id) ? "selected" : ""}>${esc(l.name)} (${l.size})</option>`).join("")}</select>
      <div id="bulkbar" class="row" style="margin-left:auto"></div>
    </div>
  </div>
  <div class="card"><div class="tbl-wrap"><table>
    <thead><tr><th class="tight"><input type="checkbox" id="chk-all"></th><th>Name</th><th>Email</th>
      <th>Phone</th><th>LinkedIn</th><th>Company</th><th>Status</th><th></th></tr></thead>
    <tbody>${data.rows.map(contactRow).join("") || `<tr><td colspan="8"><div class="empty">
      <h3>No contacts yet</h3><p>Import a CSV from Clay, Apollo, a scrape — anything with emails, phones or LinkedIn URLs.</p>
      <button class="btn" onclick="document.getElementById('c-import').click()">Import CSV</button></div></td></tr>`}</tbody>
  </table></div>
  ${data.total > 100 ? `<div class="spread" style="padding:10px 14px">
    <span class="muted sm">${contactFilter.offset + 1}–${Math.min(contactFilter.offset + 100, data.total)} of ${data.total}</span>
    <span class="row"><button class="btn ghost sm" id="pg-prev" ${contactFilter.offset ? "" : "disabled"}>Prev</button>
    <button class="btn ghost sm" id="pg-next" ${contactFilter.offset + 100 >= data.total ? "disabled" : ""}>Next</button></span></div>` : ""}
  </div>`;

  const apply = (patch) => { Object.assign(contactFilter, patch, { offset: 0 }); sel.clear(); route(); };
  let timer;
  $("#f-search").oninput = (e) => { clearTimeout(timer); const v = e.target.value; timer = setTimeout(() => apply({ search: v }), 300); };
  $("#f-status").onchange = (e) => apply({ status: e.target.value });
  $("#f-has").onchange = (e) => apply({ has: e.target.value });
  $("#f-list").onchange = (e) => apply({ list_id: e.target.value });
  if ($("#pg-prev")) $("#pg-prev").onclick = () => { contactFilter.offset -= 100; route(); };
  if ($("#pg-next")) $("#pg-next").onclick = () => { contactFilter.offset += 100; route(); };
  $("#c-import").onclick = importModal;
  $("#c-new").onclick = () => contactModal(null);
  $("#chk-all").onchange = (e) => {
    $$(".chk-row").forEach((c) => { c.checked = e.target.checked; c.checked ? sel.add(+c.dataset.id) : sel.delete(+c.dataset.id); });
    drawBulk(campaigns);
  };
  $$(".chk-row").forEach((c) => c.onchange = () => { c.checked ? sel.add(+c.dataset.id) : sel.delete(+c.dataset.id); drawBulk(campaigns); });
  $$("[data-open]").forEach((b) => b.onclick = () => contactModal(+b.dataset.open));
  drawBulk(campaigns);
};

const contactRow = (c) => `<tr>
  <td class="tight"><input type="checkbox" class="chk-row" data-id="${c.id}" ${sel.has(c.id) ? "checked" : ""}></td>
  <td><div class="row" style="gap:9px;flex-wrap:nowrap"><div class="avatar">${esc(initials(c))}</div>
    <div style="min-width:0"><strong>${esc(fullName(c))}</strong><div class="muted xs">${esc(c.title || "")}</div></div></div></td>
  <td class="sm">${c.email ? esc(c.email) : '<span class="muted xs">—</span>'}</td>
  <td class="sm">${c.phone ? esc(c.phone) : '<span class="muted xs">—</span>'}</td>
  <td class="sm">${c.linkedin_url ? `<a href="${esc(c.linkedin_url)}" target="_blank" rel="noopener" class="tag linkedin">profile</a>` : '<span class="muted xs">—</span>'}</td>
  <td class="sm">${esc(c.company || "")}</td>
  <td>${statusTag(c.status)}</td>
  <td class="tight"><button class="btn ghost sm" data-open="${c.id}">Open</button></td></tr>`;

function drawBulk(campaigns) {
  const bar = $("#bulkbar");
  if (!bar) return;
  if (!sel.size) { bar.innerHTML = '<span class="muted sm">Select rows for bulk actions</span>'; return; }
  bar.innerHTML = `<span class="tag">${sel.size} selected</span>
    <select id="b-camp" style="width:190px"><option value="">Enroll in campaign…</option>
      ${campaigns.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select>
    <button class="btn ghost sm" id="b-list">Add to list</button>
    <button class="btn ghost sm" id="b-unsub">Opt out</button>
    <button class="btn ghost sm" id="b-del">Delete</button>`;
  $("#b-camp").onchange = async (e) => {
    if (!e.target.value) return;
    const r = await api.post("/api/contacts/bulk", { action: "enroll", ids: [...sel], campaign_id: +e.target.value });
    toast(`Enrolled ${r.added || 0}, skipped ${r.skipped || 0}`); sel.clear(); route();
  };
  $("#b-list").onclick = async () => {
    const name = prompt("List name"); if (!name) return;
    await api.post("/api/contacts/bulk", { action: "add_to_list", ids: [...sel], list_name: name });
    toast("Added to " + name); sel.clear(); route();
  };
  $("#b-unsub").onclick = async () => {
    if (!confirm(`Opt out ${sel.size} contacts? They are suppressed from all future sends.`)) return;
    await api.post("/api/contacts/bulk", { action: "unsubscribe", ids: [...sel] }); sel.clear(); route();
  };
  $("#b-del").onclick = async () => {
    if (!confirm(`Permanently delete ${sel.size} contacts?`)) return;
    await api.post("/api/contacts/bulk", { action: "delete", ids: [...sel] }); sel.clear(); route();
  };
}

async function contactModal(id) {
  const c = id ? await api.get("/api/contacts/" + id) : { custom: "{}", messages: [], tasks: [], enrollments: [] };
  let custom = {};
  try { custom = JSON.parse(c.custom || "{}"); } catch (e) { custom = {}; }
  const f = (k, label, type = "text") => `<label class="f"><span>${label}</span>
    <input type="${type}" data-k="${k}" value="${esc(c[k] || "")}"></label>`;
  const m = modal({
    title: id ? fullName(c) : "New contact",
    wide: !!id,
    body: `<div class="grid" style="grid-template-columns:${id ? "1fr 1fr" : "1fr"}">
      <div>
        <div class="grid" style="grid-template-columns:1fr 1fr">${f("first_name", "First name")}${f("last_name", "Last name")}</div>
        ${f("email", "Email")}
        <div class="grid" style="grid-template-columns:1fr 1fr">${f("phone", "Phone")}${f("linkedin_url", "LinkedIn URL")}</div>
        <div class="grid" style="grid-template-columns:1fr 1fr">${f("company", "Company")}${f("title", "Title")}</div>
        ${f("website", "Website")}
        <label class="f"><span>Status</span><select data-k="status">
          ${["new", "active", "replied", "bounced", "unsubscribed", "do_not_contact", "finished"]
            .map((s) => `<option ${c.status === s ? "selected" : ""}>${s}</option>`).join("")}</select></label>
        ${Object.keys(custom).length ? `<h3 style="margin-top:12px">Custom fields from CSV</h3>
          <div class="muted xs" style="line-height:2">${Object.entries(custom).map(([k, v]) =>
            `<code class="tok">{{${esc(k)}}}</code> ${esc(String(v).slice(0, 60))}`).join("<br>")}</div>` : ""}
      </div>
      ${id ? `<div>
        <h3>Activity</h3>
        ${c.enrollments.map((e) => `<div class="spread sm" style="padding:4px 0"><span>${esc(e.campaign_name)}</span>
          <span class="tag">${esc(e.status)} · step ${e.step_index + 1}</span></div>`).join("") || '<p class="muted sm">Not in any campaign.</p>'}
        <div style="max-height:300px;overflow:auto;margin-top:10px">
        ${c.messages.slice(-12).reverse().map(msgBubble).join("") || '<p class="muted sm">No messages yet.</p>'}</div>
      </div>` : ""}
    </div>`,
    footer: `${id ? '<button class="btn ghost" id="c-open-inbox">Open in inbox</button>' : ""}
      <button class="btn ghost" data-close>Cancel</button><button class="btn" id="c-save">Save</button>`,
  });
  if (id) $("#c-open-inbox").onclick = () => { closeModal(); location.hash = "#/inbox/" + id; };
  $("#c-save").onclick = async () => {
    const payload = {};
    $$("[data-k]", m).forEach((i) => (payload[i.dataset.k] = i.value));
    await api.post(id ? "/api/contacts/" + id : "/api/contacts", payload);
    closeModal(); toast("Saved"); route();
  };
}

const msgBubble = (m) => `<div class="bubble ${m.direction === "in" ? "in" : ""}">
  <div class="meta">${chanTag(m.channel)} ${m.direction === "in" ? "received" : "sent"} ${when(m.created_at)}
  ${m.status === "dry_run" ? '<span class="tag warn">dry run</span>' : ""}
  ${m.status === "failed" ? '<span class="tag bad">failed</span>' : ""}
  ${m.open_count ? `<span class="tag ok">opened ${m.open_count}×</span>` : ""}</div>
  ${m.subject ? `<strong>${esc(m.subject)}</strong><br>` : ""}${esc((m.body || "").slice(0, 1200))}</div>`;

/* ------------------------------------------------------------------ import */
function importModal() {
  const m = modal({
    title: "Import contacts from CSV",
    wide: true,
    body: `<div id="imp-step1">
      <p class="sub">Any CSV works — Clay exports, Apollo, Sales Nav scrapes, a spreadsheet. Columns are auto-mapped and you can fix them on the next screen.</p>
      <label class="f"><span>CSV file</span><input type="file" id="imp-file" accept=".csv,text/csv"></label>
      <p class="muted xs">Or paste CSV text:</p>
      <textarea id="imp-text" placeholder="first_name,last_name,email,phone,linkedin_url,company,title"></textarea>
      <button class="btn" id="imp-parse" style="margin-top:10px">Continue</button>
      <button class="btn ghost" id="imp-sample" style="margin-top:10px">Load sample data</button>
    </div><div id="imp-step2"></div>`,
  });
  let text = "";
  $("#imp-file").onchange = (e) => {
    const file = e.target.files[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { text = reader.result; $("#imp-text").value = text.slice(0, 4000); };
    reader.readAsText(file);
  };
  $("#imp-sample").onclick = () => {
    text = `first_name,last_name,email,phone,linkedin_url,company,title,icp_note
Maya,Ortiz,maya@northwind.io,+15551234567,https://linkedin.com/in/mayaortiz,Northwind,VP Sales,hiring 3 AEs
Dev,Patel,dev@lumenics.com,,https://linkedin.com/in/devpatel,Lumenics,Head of Growth,uses Clay
Sara,Kim,,+15559876543,https://linkedin.com/in/sarakim,Brightpath,Founder,no email found
Tom,Weber,tom@zephyrlabs.co,+15553334444,,Zephyr Labs,COO,series A
Ana,Rossi,ana@finchpay.eu,,,Finchpay,CRO,inbound lead`;
    $("#imp-text").value = text; toast("Sample loaded — 5 contacts with gaps to show the waterfall");
  };
  $("#imp-parse").onclick = async () => {
    const payload = text && $("#imp-text").value.length >= 4000 ? text : $("#imp-text").value;
    if (!payload.trim()) return toast("Pick a file or paste CSV first", true);
    text = payload;
    const pre = await api.post("/api/import/preview", { csv: payload });
    if (!pre.ok) return toast(pre.error || "Could not parse CSV", true);
    $("#imp-step1").style.display = "none";
    $("#imp-step2").innerHTML = `
      <p class="sub">~${pre.approx_rows} rows. Unmapped columns are kept as custom fields you can use as <code class="tok">{{merge_tags}}</code>.</p>
      <div class="tbl-wrap" style="max-height:320px"><table><thead><tr><th>CSV column</th><th>Maps to</th><th>Sample</th></tr></thead>
      <tbody>${pre.headers.map((h) => `<tr><td class="sm"><strong>${esc(h)}</strong></td>
        <td><select data-h="${esc(h)}" style="width:170px">
          ${pre.fields.map((f) => `<option value="${f}" ${pre.mapping[h] === f ? "selected" : ""}>${f === "custom" ? "custom field" : f}</option>`).join("")}
        </select></td>
        <td class="muted sm">${esc((pre.rows[0] || {})[h] || "")}</td></tr>`).join("")}</tbody></table></div>
      <div class="row" style="margin-top:14px">
        <label class="f" style="flex:1"><span>Save as list (optional)</span><input type="text" id="imp-list" placeholder="e.g. Q3 SaaS founders"></label>
        <label class="check" style="margin-bottom:10px"><input type="checkbox" id="imp-dedupe" checked> Skip/merge duplicates by email + LinkedIn</label>
      </div>
      <button class="btn" id="imp-go">Import contacts</button>`;
    $("#imp-go").onclick = async () => {
      const mapping = {};
      $$("[data-h]").forEach((s) => (mapping[s.dataset.h] = s.value));
      $("#imp-go").disabled = true; $("#imp-go").textContent = "Importing…";
      const r = await api.post("/api/import/commit", {
        csv: text, mapping, list_name: $("#imp-list").value.trim(), dedupe: $("#imp-dedupe").checked });
      closeModal();
      toast(`Imported ${r.created} new, updated ${r.updated}, skipped ${r.skipped}`);
      contactFilter.offset = 0; location.hash = "#/contacts"; route();
    };
  };
}

/* --------------------------------------------------------------- sequences */
const STARTER_STEPS = [
  { channel: "email", delay_days: 0, subject: "quick question, {{first_name|there}}", requires_field: "email",
    body: "Hi {{first_name|there}},\n\nSaw {{company|your team}} and wanted to ask — how are you handling outbound right now?\n\nWe help teams like yours book more meetings without adding headcount. Worth a 10-minute look?\n\n{{signature}}" },
  { channel: "linkedin", action: "connect", delay_days: 1, requires_field: "linkedin_url",
    body: "Hi {{first_name|there}} — came across {{company|your company}} and liked what you're building. Connecting." },
  { channel: "email", delay_days: 2, subject: "re: quick question", requires_field: "email",
    body: "{{first_name|Hi}} — bumping this up in case it slipped.\n\nWorth a quick look?" },
  { channel: "call", delay_days: 1, requires_field: "phone",
    body: "Hi {{first_name|there}}, this is [you] — I emailed you earlier this week about outbound at {{company|your company}}.\n\nOpener: did I catch you at a bad time?\nHook: teams your size usually lose deals to slow follow-up. We fix that.\nAsk: 10 minutes Thursday or Friday?" },
  { channel: "linkedin", action: "message", delay_days: 1, requires_field: "linkedin_url",
    body: "{{first_name|Hey}} — tried you by email and phone. If outbound isn't a priority this quarter, just say so and I'll stop." },
  { channel: "email", delay_days: 3, subject: "closing the loop", requires_field: "email",
    body: "{{first_name|Hi}} — assuming the timing's wrong. I'll close the loop here.\n\nIf it changes, reply to this email.\n\n{{signature}}" },
];

views.sequences = async (el) => {
  const seqs = await api.get("/api/sequences");
  el.innerHTML = `
  <div class="head"><div><h1>Sequences</h1>
    <p class="sub">A waterfall of steps. If a contact is missing the data a step needs (no phone, no LinkedIn), the step is skipped and the next one runs immediately.</p></div>
    <div class="row"><button class="btn ghost" id="s-starter">Use starter waterfall</button>
    <button class="btn" id="s-new">New sequence</button></div></div>
  <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(330px,1fr))">
    ${seqs.map((s) => `<div class="card pad">
      <div class="spread"><h2 style="margin:0">${esc(s.name)}</h2><span class="tag">${s.steps.length} steps</span></div>
      <div class="row" style="margin:10px 0;gap:4px">${s.steps.map((st, i) =>
        `<span class="tag ${st.channel}" title="Step ${i + 1}: ${esc(st.subject || st.body.slice(0, 40))}">${i + 1}</span>`).join("")}</div>
      <p class="muted xs">${s.campaigns} campaign(s) using it</p>
      <div class="row" style="margin-top:10px">
        <button class="btn ghost sm" data-edit="${s.id}">Edit</button>
        <button class="btn ghost sm" data-camp="${s.id}">Launch campaign</button>
        <button class="btn ghost sm" data-del="${s.id}">Delete</button></div></div>`).join("")
      || `<div class="card pad empty"><h3>No sequences yet</h3>
          <p>Start with the 6-step email → LinkedIn → call waterfall, then edit the copy.</p></div>`}
  </div>`;
  $("#s-new").onclick = () => sequenceEditor(null);
  $("#s-starter").onclick = async () => {
    const r = await api.post("/api/sequences", { name: "Starter waterfall", steps: STARTER_STEPS });
    toast("Starter waterfall created"); sequenceEditor(r.id);
  };
  $$("[data-edit]").forEach((b) => b.onclick = () => sequenceEditor(+b.dataset.edit));
  $$("[data-camp]").forEach((b) => b.onclick = () => campaignModal(null, +b.dataset.camp));
  $$("[data-del]").forEach((b) => b.onclick = async () => {
    if (!confirm("Delete this sequence?")) return;
    const r = await api.del("/api/sequences/" + b.dataset.del);
    if (r.ok) { toast("Deleted"); route(); }
  });
};

async function sequenceEditor(id) {
  const all = await api.get("/api/sequences");
  const seq = id ? all.find((s) => s.id === id) : { name: "", steps: [] };
  let steps = (seq.steps || []).map((s) => ({ ...s }));
  const m = modal({
    title: id ? "Edit sequence" : "New sequence",
    wide: true,
    body: `<label class="f"><span>Sequence name</span><input type="text" id="sq-name" value="${esc(seq.name)}" placeholder="e.g. Founders waterfall"></label>
      <div id="sq-steps"></div>
      <div class="row" style="margin-top:8px">
        <button class="btn ghost sm" data-add="email">+ Email step</button>
        <button class="btn ghost sm" data-add="linkedin">+ LinkedIn step</button>
        <button class="btn ghost sm" data-add="call">+ Call step</button></div>
      <p class="muted xs" style="margin-top:12px">Merge tags: ${["first_name", "last_name", "company", "title", "email", "phone", "unsubscribe_url"]
        .map((t) => `<code class="tok">{{${t}}}</code>`).join(" ")} — plus any custom CSV column. Use <code class="tok">{{first_name|there}}</code> for a fallback.</p>`,
    footer: '<button class="btn ghost" data-close>Cancel</button><button class="btn" id="sq-save">Save sequence</button>',
  });

  const draw = () => {
    $("#sq-steps").innerHTML = steps.map((s, i) => `
      <div class="step ${s._open ? "open" : ""}" data-i="${i}">
        <div class="step-head">
          <span class="step-num">${i + 1}</span>
          <div class="chan-pick">${Object.keys(CHANNELS).map((c) =>
            `<button data-c="${c}" data-chan="${i}" class="${s.channel === c ? "on" : ""}">${CHANNELS[c]}</button>`).join("")}</div>
          <span class="muted sm">wait</span>
          <input type="number" min="0" value="${s.delay_days || 0}" data-d="${i}" style="width:62px"><span class="muted sm">days</span>
          <input type="number" min="0" max="23" value="${s.delay_hours || 0}" data-h="${i}" style="width:62px"><span class="muted sm">hrs</span>
          <span class="muted sm" style="flex:1;min-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.subject || (s.body || "").slice(0, 60))}</span>
          <button class="btn ghost sm" data-toggle="${i}">${s._open ? "Close" : "Edit"}</button>
          <button class="btn ghost sm" data-up="${i}" ${i ? "" : "disabled"}>↑</button>
          <button class="btn ghost sm" data-down="${i}" ${i === steps.length - 1 ? "disabled" : ""}>↓</button>
          <button class="btn ghost sm" data-rm="${i}">✕</button>
        </div>
        <div class="step-bd">
          ${s.channel === "email" ? `<label class="f"><span>Subject line</span>
            <input type="text" data-subj="${i}" value="${esc(s.subject || "")}"></label>` : ""}
          ${s.channel === "linkedin" ? `<label class="f"><span>Action</span><select data-act="${i}">
            <option value="connect" ${s.action === "connect" ? "selected" : ""}>Connection request (with note)</option>
            <option value="message" ${s.action === "message" ? "selected" : ""}>Direct message</option>
            <option value="view" ${s.action === "view" ? "selected" : ""}>Profile view only</option></select></label>` : ""}
          <label class="f"><span>${s.channel === "call" ? "Call script" : "Message"}</span>
            <textarea data-body="${i}" rows="${s.channel === "call" ? 7 : 8}">${esc(s.body || "")}</textarea></label>
          <div class="row">
            <label class="f" style="flex:1"><span>Waterfall gate — needs</span><select data-req="${i}">
              <option value="" ${!s.requires_field ? "selected" : ""}>default for channel</option>
              <option value="email" ${s.requires_field === "email" ? "selected" : ""}>email</option>
              <option value="phone" ${s.requires_field === "phone" ? "selected" : ""}>phone</option>
              <option value="linkedin_url" ${s.requires_field === "linkedin_url" ? "selected" : ""}>linkedin_url</option>
            </select></label>
            <label class="f" style="flex:1"><span>If that data is missing</span><select data-miss="${i}">
              <option value="skip" ${s.on_missing !== "stop" ? "selected" : ""}>Skip to next step now (waterfall)</option>
              <option value="stop" ${s.on_missing === "stop" ? "selected" : ""}>Stop the sequence for this contact</option>
            </select></label>
            ${s.channel === "email" ? `<label class="check" style="margin-bottom:10px;flex:1">
              <input type="checkbox" data-auto="${i}" ${s.auto_send === 0 ? "" : "checked"}> Send automatically</label>` : ""}
          </div>
          <button class="btn ghost sm" data-prev="${i}">Preview with a real contact</button>
        </div>
      </div>`).join("") || '<p class="muted sm">Add your first step below.</p>';

    $$("[data-chan]", m).forEach((b) => b.onclick = () => { steps[+b.dataset.chan].channel = b.dataset.c; draw(); });
    $$("[data-toggle]", m).forEach((b) => b.onclick = () => { const i = +b.dataset.toggle; steps[i]._open = !steps[i]._open; draw(); });
    $$("[data-rm]", m).forEach((b) => b.onclick = () => { steps.splice(+b.dataset.rm, 1); draw(); });
    $$("[data-up]", m).forEach((b) => b.onclick = () => { const i = +b.dataset.up; [steps[i - 1], steps[i]] = [steps[i], steps[i - 1]]; draw(); });
    $$("[data-down]", m).forEach((b) => b.onclick = () => { const i = +b.dataset.down; [steps[i + 1], steps[i]] = [steps[i], steps[i + 1]]; draw(); });
    const bind = (attr, key, num) => $$(`[data-${attr}]`, m).forEach((inp) => {
      inp.oninput = inp.onchange = () => {
        const i = +inp.dataset[attr];
        steps[i][key] = num ? +inp.value : (inp.type === "checkbox" ? (inp.checked ? 1 : 0) : inp.value);
      };
    });
    bind("d", "delay_days", true); bind("h", "delay_hours", true); bind("subj", "subject");
    bind("body", "body"); bind("req", "requires_field"); bind("miss", "on_missing");
    bind("act", "action"); bind("auto", "auto_send");
    $$("[data-prev]", m).forEach((b) => b.onclick = async () => {
      const s = steps[+b.dataset.prev];
      const r = await api.post("/api/preview", { subject: s.subject || "", body: s.body || "" });
      alert(`Preview for ${r.contact.name || "a sample contact"}\n\n` +
        (r.subject ? "Subject: " + r.subject + "\n\n" : "") + r.body +
        (r.missing.length ? "\n\n⚠ Empty merge tags: " + r.missing.join(", ") + " — add |fallbacks" : ""));
    });
  };
  draw();
  $$("[data-add]", m).forEach((b) => b.onclick = () => {
    steps.push({ channel: b.dataset.add, delay_days: steps.length ? 2 : 0, delay_hours: 0,
      subject: "", body: "", requires_field: "", on_missing: "skip", auto_send: 1, action: "message", _open: true });
    draw();
  });
  $("#sq-save").onclick = async () => {
    const name = $("#sq-name").value.trim();
    if (!name) return toast("Name the sequence first", true);
    if (!steps.length) return toast("Add at least one step", true);
    await api.post(id ? "/api/sequences/" + id : "/api/sequences", { name, steps });
    closeModal(); toast("Sequence saved"); route();
  };
}

/* --------------------------------------------------------------- campaigns */
views.campaigns = async (el) => {
  const [camps, seqs] = await Promise.all([api.get("/api/campaigns"), api.get("/api/sequences")]);
  el.innerHTML = `
  <div class="head"><div><h1>Campaigns</h1><p class="sub">A sequence plus a list of people, sending limits and hours.</p></div>
    <button class="btn" id="cp-new" ${seqs.length ? "" : "disabled"}>New campaign</button></div>
  ${seqs.length ? "" : '<div class="card pad empty"><h3>Build a sequence first</h3><p><a href="#/sequences">Go to sequences →</a></p></div>'}
  <div class="stack">${camps.map((c) => {
    const s = c.stats;
    const done = (s.finished || 0) + (s.replied || 0);
    return `<div class="card pad">
      <div class="spread">
        <div><div class="row"><h2 style="margin:0">${esc(c.name)}</h2>
          <span class="tag ${c.status === "running" ? "ok" : c.status === "paused" ? "warn" : ""}">${esc(c.status)}</span></div>
          <p class="muted xs" style="margin:4px 0 0">${esc(c.sequence_name)} · ${c.daily_limit}/day ·
          ${c.window_start}:00–${c.window_end}:00${c.weekdays_only ? " · weekdays" : ""}${c.stop_on_reply ? " · stops on reply" : ""}</p></div>
        <div class="row">
          <button class="btn ghost sm" data-enroll="${c.id}">Add contacts</button>
          ${c.status === "running"
            ? `<button class="btn ghost sm" data-pause="${c.id}">Pause</button>`
            : `<button class="btn sm" data-start="${c.id}">${c.status === "paused" ? "Resume" : "Start"}</button>`}
          <button class="btn ghost sm" data-edit="${c.id}">Edit</button>
          <button class="btn ghost sm" data-del="${c.id}">Delete</button></div></div>
      <div class="kpis" style="margin-top:12px">
        ${kpi(s.total, "Enrolled", "")}${kpi(s.active, "Active", "")}${kpi(s.waiting, "Awaiting your action", "")}
        ${kpi(s.replied, "Replied", pct(s.replied, s.total) + "%")}${kpi(c.sent_today, "Sent today", "limit " + c.daily_limit)}</div>
      <div class="bar" style="margin-top:12px"><i style="width:${pct(done, s.total)}%"></i></div>
    </div>`;
  }).join("") || (seqs.length ? '<div class="card pad empty"><h3>No campaigns yet</h3><p>Create one to start the waterfall.</p></div>' : "")}
  </div>`;
  if ($("#cp-new")) $("#cp-new").onclick = () => campaignModal(null);
  $$("[data-start]").forEach((b) => b.onclick = async () => {
    await api.post(`/api/campaigns/${b.dataset.start}/status`, { status: "running" }); toast("Campaign running"); route(); });
  $$("[data-pause]").forEach((b) => b.onclick = async () => {
    await api.post(`/api/campaigns/${b.dataset.pause}/status`, { status: "paused" }); toast("Paused"); route(); });
  $$("[data-edit]").forEach((b) => b.onclick = () => campaignModal(+b.dataset.edit));
  $$("[data-enroll]").forEach((b) => b.onclick = () => enrollModal(+b.dataset.enroll));
  $$("[data-del]").forEach((b) => b.onclick = async () => {
    if (!confirm("Delete campaign and its enrollments?")) return;
    await api.del("/api/campaigns/" + b.dataset.del); route(); });
};

async function campaignModal(id, presetSeq) {
  const [camps, seqs] = await Promise.all([api.get("/api/campaigns"), api.get("/api/sequences")]);
  const c = id ? camps.find((x) => x.id === id) : {
    name: "", sequence_id: presetSeq || (seqs[0] || {}).id, daily_limit: 50,
    window_start: 8, window_end: 18, weekdays_only: 1, stop_on_reply: 1 };
  modal({
    title: id ? "Edit campaign" : "New campaign",
    body: `<label class="f"><span>Campaign name</span><input type="text" id="cp-name" value="${esc(c.name)}" placeholder="e.g. PH founders — September"></label>
      <label class="f"><span>Sequence</span><select id="cp-seq">${seqs.map((s) =>
        `<option value="${s.id}" ${s.id === c.sequence_id ? "selected" : ""}>${esc(s.name)} (${s.steps.length} steps)</option>`).join("")}</select></label>
      <div class="grid" style="grid-template-columns:1fr 1fr 1fr">
        <label class="f"><span>Emails per day</span><input type="number" id="cp-limit" value="${c.daily_limit}" min="1"></label>
        <label class="f"><span>Send from (hour)</span><input type="number" id="cp-ws" value="${c.window_start}" min="0" max="23"></label>
        <label class="f"><span>Send until (hour)</span><input type="number" id="cp-we" value="${c.window_end}" min="1" max="24"></label>
      </div>
      <label class="check" style="margin-bottom:8px"><input type="checkbox" id="cp-wd" ${c.weekdays_only ? "checked" : ""}> Weekdays only</label>
      <label class="check"><input type="checkbox" id="cp-sr" ${c.stop_on_reply ? "checked" : ""}> Stop the whole waterfall when someone replies on any channel</label>`,
    footer: '<button class="btn ghost" data-close>Cancel</button><button class="btn" id="cp-save">Save</button>',
  });
  $("#cp-save").onclick = async () => {
    const payload = {
      name: $("#cp-name").value.trim(), sequence_id: +$("#cp-seq").value,
      daily_limit: +$("#cp-limit").value, window_start: +$("#cp-ws").value, window_end: +$("#cp-we").value,
      weekdays_only: $("#cp-wd").checked, stop_on_reply: $("#cp-sr").checked };
    if (!payload.name) return toast("Name the campaign", true);
    const r = await api.post(id ? "/api/campaigns/" + id : "/api/campaigns", payload);
    closeModal(); toast("Saved");
    if (!id && r.id) enrollModal(r.id); else route();
  };
}

async function enrollModal(campaignId) {
  const lists = await api.get("/api/lists");
  modal({
    title: "Add contacts to campaign",
    body: `<label class="f"><span>From a list</span><select id="en-list"><option value="">— pick a list —</option>
      ${lists.map((l) => `<option value="${l.id}">${esc(l.name)} (${l.size})</option>`).join("")}</select></label>
      <p class="muted sm">or add everyone matching a filter:</p>
      <div class="row">
        <select id="en-status" style="flex:1"><option value="">Any status</option>
          ${["new", "active", "replied"].map((s) => `<option>${s}</option>`).join("")}</select>
        <select id="en-has" style="flex:1"><option value="">Any data</option>
          <option value="email">Has email</option><option value="phone">Has phone</option>
          <option value="linkedin_url">Has LinkedIn</option></select>
      </div>
      <p class="muted xs" style="margin-top:10px">Contacts already enrolled, opted out or bounced are skipped automatically.</p>`,
    footer: '<button class="btn ghost" data-close>Cancel</button><button class="btn" id="en-go">Add to campaign</button>',
  });
  $("#en-go").onclick = async () => {
    const body = { contact_ids: [] };
    if ($("#en-list").value) body.list_id = +$("#en-list").value;
    else {
      body.all_matching = true;
      body.filter = {};
      if ($("#en-status").value) body.filter.status = $("#en-status").value;
      if ($("#en-has").value) body.filter.has = $("#en-has").value;
    }
    const r = await api.post(`/api/campaigns/${campaignId}/enroll`, body);
    closeModal(); toast(`Added ${r.added || 0} contacts (${r.skipped || 0} skipped)`);
    location.hash = "#/campaigns"; route();
  };
}

/* ------------------------------------------------------------ today's queue */
const DISPOSITIONS = ["Connected — interested", "Connected — not now", "Connected — not a fit",
  "Left voicemail", "No answer", "Gatekeeper", "Wrong number", "Booked meeting"];
let taskFilter = "";
let currentTask = null;

views.tasks = async (el, arg) => {
  const data = await api.get("/api/tasks?status=pending" + (taskFilter ? "&channel=" + taskFilter : ""));
  const rows = data.rows;
  currentTask = rows.find((r) => String(r.id) === String(arg)) || rows[0] || null;
  el.innerHTML = `
  <div class="head"><div><h1>Today's queue</h1>
    <p class="sub">Everything the waterfall scheduled for a human: LinkedIn touches, calls and manual emails.</p></div>
    <div class="row">
      ${["", "call", "linkedin", "email"].map((c) => `<button class="btn ${taskFilter === c ? "" : "ghost"} sm" data-f="${c}">
        ${c ? CHANNELS[c] : "All"}${data.counts[c] ? ` (${data.counts[c]})` : c === "" ? ` (${rows.length})` : ""}</button>`).join("")}
    </div></div>
  ${rows.length ? `<div class="split">
    <div class="list-pane">${rows.map((r) => `<div class="li ${currentTask && r.id === currentTask.id ? "sel" : ""}" data-t="${r.id}">
      <div class="avatar">${esc(initials(r))}</div>
      <div style="min-width:0;flex:1">
        <div class="spread"><span class="nm">${esc(fullName(r))}</span>${chanTag(r.channel)}</div>
        <div class="mt">${esc(r.title || "")}${r.company ? " · " + esc(r.company) : ""}</div>
        <div class="mt">${esc(r.campaign_name || "ad hoc")} · step ${r.step_index + 1}</div>
      </div></div>`).join("")}</div>
    <div id="cockpit" class="card pad"></div>
  </div>` : `<div class="card pad empty"><h3>Queue is clear</h3>
      <p>No LinkedIn or call tasks are due. Start a campaign, or run the scheduler from the sidebar.</p></div>`}`;
  $$("[data-f]").forEach((b) => b.onclick = () => { taskFilter = b.dataset.f; route(); });
  $$("[data-t]").forEach((b) => b.onclick = () => { currentTask = rows.find((r) => r.id === +b.dataset.t); drawCockpit(); 
    $$(".li").forEach((x) => x.classList.toggle("sel", x === b)); });
  drawCockpit();
};

function drawCockpit() {
  const el = $("#cockpit");
  if (!el || !currentTask) return;
  const t = currentTask;
  const isCall = t.channel === "call";
  const isLi = t.channel === "linkedin";
  el.innerHTML = `
    <div class="spread" style="margin-bottom:14px">
      <div class="row"><div class="avatar" style="width:38px;height:38px;flex:0 0 38px;font-size:13px">${esc(initials(t))}</div>
        <div><h2 style="margin:0">${esc(fullName(t))}</h2>
          <p class="muted xs" style="margin:2px 0 0">${esc(t.title || "")}${t.company ? " · " + esc(t.company) : ""} · ${esc(t.campaign_name || "ad hoc")} step ${t.step_index + 1}</p></div></div>
      <div class="row">${chanTag(t.channel)}${t.action && t.action !== "message" ? `<span class="tag">${esc(t.action)}</span>` : ""}</div>
    </div>
    <div class="row" style="margin-bottom:14px">
      ${t.phone ? `<a class="btn sm ${isCall ? "" : "ghost"}" href="tel:${esc(t.phone)}">Call ${esc(t.phone)}</a>` : ""}
      ${t.linkedin_url ? `<a class="btn sm ${isLi ? "" : "ghost"}" href="${esc(t.linkedin_url)}" target="_blank" rel="noopener">Open LinkedIn profile</a>` : ""}
      ${t.email ? `<span class="tag">${esc(t.email)}</span>` : ""}
      <a class="btn ghost sm" href="#/inbox/${t.contact_id}">Full history</a>
    </div>
    ${t.subject && !isCall ? `<label class="f"><span>Subject</span><input type="text" id="tk-subj" value="${esc(t.subject)}"></label>` : ""}
    <label class="f"><span>${isCall ? "Call script — edit freely, it saves with the call log" : "Message"}</span>
      <textarea id="tk-body" rows="${isCall ? 9 : 7}">${esc(t.body || "")}</textarea></label>
    <div class="row" style="margin-bottom:14px">
      <button class="btn ghost sm" id="tk-copy">Copy message</button>
      ${isLi ? '<span class="muted xs">Paste it into LinkedIn, then log the result below.</span>' : ""}
      ${t.channel === "email" ? '<span class="muted xs">Sends through your configured mailbox.</span>' : ""}
    </div>
    ${isCall ? `<h3>Log the call</h3><div class="disp" style="margin-bottom:12px">
      ${DISPOSITIONS.map((d) => `<button data-disp="${esc(d)}">${esc(d)}</button>`).join("")}</div>
      <label class="f"><span>Notes</span><textarea id="tk-notes" rows="3" placeholder="What did they say? Next step?"></textarea></label>` : ""}
    ${isLi ? `<h3>Log the result</h3><div class="disp" style="margin-bottom:12px">
      ${["Request sent", "Message sent", "Accepted", "Replied", "Profile viewed"].map((d) =>
        `<button data-disp="${esc(d)}">${esc(d)}</button>`).join("")}</div>` : ""}
    <div class="row" style="margin-top:6px">
      <button class="btn" id="tk-done">${t.channel === "email" ? "Send email" : "Mark done"}</button>
      <button class="btn ghost" id="tk-snooze">Snooze 1 day</button>
      <button class="btn ghost" id="tk-skip">Skip step</button>
      <button class="btn ghost" id="tk-reply">They replied</button>
    </div>
    <p class="muted xs" style="margin-top:10px">Completing this advances the contact to the next step of the waterfall.</p>`;

  let disposition = "";
  $$("[data-disp]", el).forEach((b) => b.onclick = () => {
    disposition = b.dataset.disp;
    $$("[data-disp]", el).forEach((x) => (x.style.borderColor = "", x.style.color = ""));
    b.style.borderColor = "var(--brand)"; b.style.color = "var(--brand)";
  });
  $("#tk-copy").onclick = async () => {
    try { await navigator.clipboard.writeText($("#tk-body").value); toast("Copied"); }
    catch (e) { $("#tk-body").select(); document.execCommand("copy"); toast("Copied"); }
  };
  $("#tk-done").onclick = async () => {
    const r = await api.post(`/api/tasks/${t.id}/complete`, {
      outcome: disposition || (t.channel === "email" ? "sent" : "done"),
      notes: $("#tk-notes") ? $("#tk-notes").value : "",
      body: $("#tk-body").value });
    if (r.ok) { toast("Logged — contact moved to the next step"); route(); }
  };
  $("#tk-skip").onclick = async () => {
    await api.post(`/api/tasks/${t.id}/skip`, { reason: "manually skipped" }); toast("Skipped"); route(); };
  $("#tk-snooze").onclick = async () => {
    await api.post(`/api/tasks/${t.id}/snooze`, { hours: 24 }); toast("Snoozed 1 day"); route(); };
  $("#tk-reply").onclick = async () => {
    const text = prompt("What did they say? (logged to the inbox and stops the sequence)");
    if (text === null) return;
    await api.post(`/api/inbox/${t.contact_id}/log`, { channel: t.channel, body: text, mark_replied: true });
    await api.post(`/api/tasks/${t.id}/complete`, { outcome: "replied", body: $("#tk-body").value });
    toast("Reply logged"); route();
  };
}

/* ------------------------------------------------------------ master inbox */
let inboxFilter = "all";

views.inbox = async (el, arg) => {
  const data = await api.get("/api/inbox?filter=" + inboxFilter);
  const rows = data.rows;
  const activeId = arg ? +arg : (rows[0] ? rows[0].contact_id : null);
  el.innerHTML = `
  <div class="head"><div><h1>Master inbox</h1>
    <p class="sub">Every conversation, every channel, one thread per person.</p></div>
    <div class="row">
      ${["all", "unread", "replied", "email", "linkedin", "call"].map((f) =>
        `<button class="btn ${inboxFilter === f ? "" : "ghost"} sm" data-if="${f}">${f}</button>`).join("")}
      <button class="btn ghost sm" id="ib-sync">Sync email</button>
    </div></div>
  ${rows.length ? `<div class="split">
    <div class="list-pane">${rows.map((r) => `<div class="li ${r.unread ? "unread" : ""} ${r.contact_id === activeId ? "sel" : ""}" data-c="${r.contact_id}">
      <div class="avatar">${esc(initials(r))}</div>
      <div style="min-width:0;flex:1">
        <div class="spread"><span class="nm">${esc(fullName(r))}</span>
          <span class="muted xs">${when(r.last_message_at)}</span></div>
        <div class="mt">${r.last_direction === "in" ? "↙ " : "↗ "}${esc(r.snippet || "")}</div>
        <div class="row" style="gap:4px;margin-top:3px">${chanTag(r.last_channel)}${statusTag(r.contact_status)}</div>
      </div></div>`).join("")}</div>
    <div id="thread" class="card pad"></div></div>`
  : `<div class="card pad empty"><h3>No conversations yet</h3>
     <p>Sent emails, LinkedIn messages and logged calls all land here.</p></div>`}`;
  $$("[data-if]").forEach((b) => b.onclick = () => { inboxFilter = b.dataset.if; location.hash = "#/inbox"; route(); });
  $("#ib-sync").onclick = async () => {
    toast("Checking mailbox…");
    const r = await api.post("/api/inbox/sync", {});
    toast(r.ok ? `Imported ${r.imported} replies` : r.error, !r.ok);
    if (r.ok) route();
  };
  $$("[data-c]").forEach((b) => b.onclick = () => { history.replaceState(null, "", "#/inbox/" + b.dataset.c); openThread(+b.dataset.c); 
    $$(".li").forEach((x) => x.classList.toggle("sel", x === b)); b.classList.remove("unread"); });
  if (activeId) openThread(activeId);
};

async function openThread(contactId) {
  const el = $("#thread");
  if (!el) return;
  el.innerHTML = '<div class="loading">Loading…</div>';
  const c = await api.get("/api/inbox/" + contactId);
  const avail = ["email", "linkedin", "call"].filter((ch) =>
    ch === "email" ? !!c.email : ch === "linkedin" ? !!c.linkedin_url : !!c.phone);
  if (!avail.length) avail.push("email");
  el.innerHTML = `
    <div class="spread" style="margin-bottom:12px">
      <div class="row"><div class="avatar" style="width:38px;height:38px;flex:0 0 38px">${esc(initials(c))}</div>
        <div><h2 style="margin:0">${esc(fullName(c))}</h2>
          <p class="muted xs" style="margin:2px 0 0">${esc(c.title || "")}${c.company ? " · " + esc(c.company) : ""}
          ${c.email ? " · " + esc(c.email) : ""}${c.phone ? " · " + esc(c.phone) : ""}</p></div></div>
      <div class="row">
        ${c.linkedin_url ? `<a class="btn ghost sm" href="${esc(c.linkedin_url)}" target="_blank" rel="noopener">LinkedIn</a>` : ""}
        ${c.phone ? `<a class="btn ghost sm" href="tel:${esc(c.phone)}">Call</a>` : ""}
        <select id="th-status" class="sm" style="width:150px">
          ${["new", "active", "replied", "finished", "do_not_contact", "unsubscribed"].map((s) =>
            `<option ${c.status === s ? "selected" : ""}>${s}</option>`).join("")}</select>
      </div></div>
    ${c.enrollments.length ? `<div class="row" style="margin-bottom:10px">${c.enrollments.map((e) =>
      `<span class="tag ${e.status === "replied" ? "ok" : ""}">${esc(e.campaign_name)}: ${esc(e.status)} (step ${e.step_index + 1})</span>`).join("")}</div>` : ""}
    <div id="th-scroll" style="max-height:44vh;overflow:auto;margin-bottom:14px">
      ${c.messages.map(msgBubble).join("") || '<p class="muted sm">No messages yet.</p>'}</div>
    <div class="card pad" style="background:var(--panel-2)">
      <div class="row" style="margin-bottom:8px">
        ${avail.map((ch, i) => `<button class="btn ${i ? "ghost" : ""} sm" data-rc="${ch}">${CHANNELS[ch]}</button>`).join("")}
        <span style="margin-left:auto"></span>
        <button class="btn ghost sm" id="th-log">Log their reply</button>
      </div>
      <input type="text" id="th-subj" placeholder="Subject" style="margin-bottom:8px">
      <textarea id="th-body" rows="5" placeholder="Write your reply…"></textarea>
      <div class="row" style="margin-top:8px"><button class="btn" id="th-send">Send</button>
        <span class="muted xs" id="th-hint">Email goes out through your mailbox.</span></div>
    </div>`;
  let channel = avail[0];
  const scroller = $("#th-scroll", el);
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
  if (channel !== "email") {
    $("#th-subj").style.display = "none";
    $("#th-hint").textContent = channel === "linkedin"
      ? "Logged as a LinkedIn message you send manually." : "Logged as a call you made.";
  }
  $$("[data-rc]", el).forEach((b) => b.onclick = () => {
    channel = b.dataset.rc;
    $$("[data-rc]", el).forEach((x) => x.classList.toggle("ghost", x !== b));
    $("#th-subj").style.display = channel === "email" ? "" : "none";
    $("#th-hint").textContent = channel === "email" ? "Email goes out through your mailbox."
      : channel === "linkedin" ? "Logged as a LinkedIn message you send manually."
      : "Logged as a call you made.";
  });
  $("#th-send").onclick = async () => {
    const body = $("#th-body").value.trim();
    if (!body) return toast("Nothing to send", true);
    const r = await api.post(`/api/inbox/${contactId}/reply`, { channel, subject: $("#th-subj").value, body });
    if (r.ok) { toast("Sent"); openThread(contactId); }
  };
  $("#th-log").onclick = async () => {
    const text = prompt("What did they say? (LinkedIn DM, callback, forwarded reply)");
    if (!text) return;
    await api.post(`/api/inbox/${contactId}/log`, { channel, body: text, mark_replied: true });
    toast("Logged as a reply — sequences stopped"); openThread(contactId);
  };
  $("#th-status").onchange = async (e) => {
    await api.post(`/api/inbox/${contactId}/state`, { contact_status: e.target.value });
    toast("Status updated");
  };
}

/* ----------------------------------------------------------------- reports */
views.reports = async (el) => {
  const days = +(localStorage.getItem("rep_days") || 30);
  const campaignId = localStorage.getItem("rep_camp") || "";
  const [rep, camps] = await Promise.all([
    api.get(`/api/reports?days=${days}${campaignId ? "&campaign_id=" + campaignId : ""}`),
    api.get("/api/campaigns")]);
  const t = rep.totals;
  const max = Math.max(1, ...rep.series.map((s) => Math.max(s.sent || 0, s.calls || 0, s.linkedin || 0)));
  el.innerHTML = `
  <div class="head"><div><h1>Reports</h1><p class="sub">Last ${days} days${campaignId ? " · single campaign" : " · all campaigns"}.</p></div>
    <div class="row">
      <select id="rp-camp" style="width:200px"><option value="">All campaigns</option>
        ${camps.map((c) => `<option value="${c.id}" ${String(c.id) === campaignId ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
      <select id="rp-days" style="width:120px">${[7, 30, 90, 365].map((d) =>
        `<option value="${d}" ${d === days ? "selected" : ""}>${d} days</option>`).join("")}</select>
      <a class="btn ghost sm" href="/api/export?what=messages">Export messages</a>
      <a class="btn ghost sm" href="/api/export?what=tasks">Export activity</a>
    </div></div>
  <div class="kpis" style="margin-bottom:16px">
    ${kpi(t.emails_sent, "Emails sent", pct(t.opens, t.emails_sent) + "% open rate")}
    ${kpi(t.linkedin_sent, "LinkedIn touches", "")}
    ${kpi(t.calls, "Calls logged", "")}
    ${kpi(t.replies, "Replies", pct(t.replies, t.reached) + "% of people touched")}
    ${kpi(t.bounces, "Bounces", pct(t.bounces, t.emails_sent) + "%")}
    ${kpi(t.unsubscribes, "Opt-outs", "")}
    ${kpi(t.skipped, "Steps skipped", "missing channel data")}
    ${kpi(t.reached, "People touched", "of " + t.contacts + " contacts")}
  </div>
  <div class="grid" style="grid-template-columns:1.4fr 1fr;margin-bottom:14px">
    <div class="card pad"><h2>Activity by day</h2>
      ${rep.series.length ? `<div class="chart">${rep.series.map((s) => `<div class="col" title="${s.d}: ${s.sent || 0} emails, ${s.linkedin || 0} LinkedIn, ${s.calls || 0} calls">
        <i style="height:${((s.replies || 0) / max) * 120}px;background:var(--ok)"></i>
        <i style="height:${((s.calls || 0) / max) * 120}px;background:var(--call);opacity:.65"></i>
        <i style="height:${((s.linkedin || 0) / max) * 120}px;background:var(--linkedin)"></i>
        <i style="height:${((s.sent || 0) / max) * 120}px;background:var(--brand)"></i></div>`).join("")}</div>
      <div class="legend"><span style="color:var(--brand)">Emails</span><span style="color:var(--linkedin)">LinkedIn</span>
        <span style="color:var(--call)">Calls</span><span style="color:var(--ok)">Replies</span></div>`
      : '<p class="muted sm">No activity in this window yet.</p>'}</div>
    <div class="card pad"><h2>Call dispositions</h2>
      ${rep.dispositions.length ? rep.dispositions.map((d) => `<div style="margin-bottom:9px">
        <div class="spread sm"><span>${esc(d.outcome || "unspecified")}</span><strong>${d.n}</strong></div>
        <div class="bar"><i style="width:${pct(d.n, rep.dispositions.reduce((a, b) => a + b.n, 0))}%;background:var(--call)"></i></div></div>`).join("")
      : '<p class="muted sm">No calls logged yet.</p>'}</div>
  </div>
  <div class="grid" style="grid-template-columns:1fr 1fr">
    <div class="card pad"><h2>Step-by-step waterfall</h2>
      <table><thead><tr><th>Step</th><th>Channel</th><th>Queued</th><th>Done</th><th>Skipped</th></tr></thead>
      <tbody>${rep.by_step.map((s) => `<tr><td>${s.step_index + 1}</td><td>${chanTag(s.channel)}</td>
        <td>${s.n}</td><td>${s.done || 0}</td><td class="muted">${s.skipped || 0}</td></tr>`).join("")
        || '<tr><td colspan="5" class="muted sm">Nothing has run yet.</td></tr>'}</tbody></table>
      <p class="muted xs" style="margin-top:8px">Skipped = contact was missing the phone / LinkedIn / email that step needs, so the waterfall moved on.</p></div>
    <div class="card pad"><h2>Campaign comparison</h2>
      <table><thead><tr><th>Campaign</th><th>Enrolled</th><th>Touches</th><th>Replied</th><th>Rate</th></tr></thead>
      <tbody>${rep.per_campaign.map((c) => `<tr><td><strong class="sm">${esc(c.name)}</strong>
        <div class="muted xs">${esc(c.status)}</div></td><td>${c.enrolled}</td><td>${c.touches}</td>
        <td>${c.replied}</td><td><strong>${pct(c.replied, c.enrolled)}%</strong></td></tr>`).join("")
        || '<tr><td colspan="5" class="muted sm">No campaigns yet.</td></tr>'}</tbody></table></div>
  </div>`;
  $("#rp-days").onchange = (e) => { localStorage.setItem("rep_days", e.target.value); route(); };
  $("#rp-camp").onchange = (e) => { localStorage.setItem("rep_camp", e.target.value); route(); };
};

/* ---------------------------------------------------------------- settings */
views.settings = async (el) => {
  const s = await api.get("/api/settings");
  const f = (k, label, type = "text", hint = "") => `<label class="f"><span>${label}</span>
    <input type="${type}" data-s="${k}" value="${esc(s[k] || "")}">${hint ? `<span class="muted xs">${hint}</span>` : ""}</label>`;
  el.innerHTML = `
  <div class="head"><div><h1>Settings</h1>
    <p class="sub">Everything runs on your machine. No third-party service is involved — email goes straight from your own mailbox.</p></div>
    <button class="btn" id="st-save">Save settings</button></div>
  <div class="grid" style="grid-template-columns:1fr 1fr">
    <div class="card pad">
      <h2>Sending mode</h2>
      <label class="check" style="margin-bottom:12px"><input type="checkbox" data-s="dry_run" ${s.dry_run === "1" ? "checked" : ""}>
        <span><strong>Dry run</strong> — record emails without delivering them (safe for testing the whole waterfall)</span></label>
      <label class="check" style="margin-bottom:12px"><input type="checkbox" data-s="engine_enabled" ${s.engine_enabled === "1" ? "checked" : ""}>
        <span><strong>Scheduler on</strong> — process due steps every 20 seconds</span></label>
      <label class="check"><input type="checkbox" data-s="track_opens" ${s.track_opens === "1" ? "checked" : ""}>
        <span><strong>Open tracking</strong> — a 1×1 pixel served by this app (no external tracker)</span></label>
      <h2 style="margin-top:18px">Identity</h2>
      ${f("from_name", "From name")}${f("from_email", "From email")}${f("reply_to", "Reply-to (optional)")}
      <label class="f"><span>Signature (appended to automated emails)</span>
        <textarea data-s="signature" rows="4">${esc(s.signature || "")}</textarea></label>
    </div>
    <div class="stack">
      <div class="card pad">
        <h2>SMTP — outgoing mail</h2>
        <p class="muted xs" style="margin-top:-4px">Gmail: smtp.gmail.com : 587, STARTTLS, and an app password. Outlook: smtp.office365.com : 587.</p>
        ${f("smtp_host", "SMTP host")}
        <div class="grid" style="grid-template-columns:1fr 1fr">${f("smtp_port", "Port", "number")}
          <label class="f"><span>Security</span><select data-s="smtp_security">
            ${["starttls", "ssl", "none"].map((o) => `<option ${s.smtp_security === o ? "selected" : ""}>${o}</option>`).join("")}</select></label></div>
        ${f("smtp_user", "Username")}${f("smtp_pass", "Password / app password", "password")}
        <div class="row"><button class="btn ghost sm" id="st-test">Send test email</button>
          <span class="muted xs">Sends one real email to your from-address.</span></div>
      </div>
      <div class="card pad">
        <h2>IMAP — reply capture</h2>
        <p class="muted xs" style="margin-top:-4px">Pulls unread replies into the master inbox and stops sequences automatically.</p>
        ${f("imap_host", "IMAP host")}
        <div class="grid" style="grid-template-columns:1fr 1fr">${f("imap_port", "Port", "number")}${f("imap_folder", "Folder")}</div>
        ${f("imap_user", "Username")}${f("imap_pass", "Password / app password", "password")}
        ${f("imap_poll_minutes", "Check every (minutes)", "number")}
      </div>
    </div>
  </div>`;
  $("#st-save").onclick = async () => {
    const payload = {};
    $$("[data-s]").forEach((i) => (payload[i.dataset.s] = i.type === "checkbox" ? (i.checked ? "1" : "0") : i.value));
    await api.post("/api/settings", payload); toast("Settings saved"); route();
  };
  $("#st-test").onclick = async () => {
    toast("Sending test…");
    const r = await api.post("/api/settings/test", {});
    toast(r.ok ? "Test email sent — check your inbox" : r.error, !r.ok);
  };
};

/* -------------------------------------------------------------------- init */
$("#btn-tick").onclick = async () => {
  const r = await api.post("/api/engine", {});
  toast(r.skipped ? "Scheduler is off (Settings)" : `Scheduler ran: ${r.processed || 0} contacts advanced, ${r.sent || 0} emails sent`);
  route();
};
setInterval(refreshBoot, 30000);
route();
