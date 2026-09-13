const projectSelect = document.getElementById("project-select");
const refreshBtn = document.getElementById("refresh-btn");
const treeEl = document.getElementById("tree");
const metaEl = document.getElementById("meta");
const titleEl = document.getElementById("project-title");
const constraintsEl = document.getElementById("constraints");
const pendingBanner = document.getElementById("pending-banner");

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatValue(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object" && v !== null) return JSON.stringify(v);
  return String(v);
}

function renderData(data) {
  if (!data || typeof data !== "object") return "";
  return Object.entries(data)
    .map(
      ([k, v]) =>
        `<span class="data-tag"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(formatValue(v))}</span>`
    )
    .join("");
}

function renderNode(node, depth = 0) {
  const children = node.children || [];
  const hasChildren = children.length > 0;
  const stale = node.stale ? " stale" : "";
  const weak = node.status === "weak" ? " node-weak" : "";
  const statusClass = `badge-status-${(node.status || "empty").replace(/-/g, "_")}`;

  const childHtml = hasChildren
    ? `<div class="children">${children.map((c) => renderNode(c, depth + 1)).join("")}</div>`
    : "";

  const title = escapeHtml(node.title || node.id);
  const nodeId = escapeHtml(node.id);
  const kind = escapeHtml(node.kind || "?");
  const status = escapeHtml(node.status || "empty");

  return `
    <div class="node${stale}${weak}" data-depth="${depth}">
      <div class="node-row" data-toggle data-status="${status}">
        <span class="toggle${hasChildren ? "" : " empty"}">${hasChildren ? "▼" : ""}</span>
        <div class="node-body">
          <div class="node-title-line">
            <span class="node-title">${title}</span>
            <span class="node-id">${nodeId}</span>
            <span class="badge badge-kind">${kind}</span>
            <span class="badge ${statusClass}">${status}</span>
            ${node.stale ? '<span class="badge badge-stale">stale</span>' : ""}
          </div>
          ${node.notes ? `<p class="node-notes">${escapeHtml(node.notes)}</p>` : ""}
          ${node.data ? `<div class="node-data">${renderData(node.data)}</div>` : ""}
        </div>
      </div>
      ${childHtml}
    </div>
  `;
}

function renderConstraints(constraints) {
  if (!constraints || Object.keys(constraints).length === 0) {
    constraintsEl.innerHTML = "";
    return;
  }
  constraintsEl.innerHTML = Object.entries(constraints)
    .map(([k, v]) => `<span class="chip"><span class="chip-muted">${k}</span> ${formatValue(v)}</span>`)
    .join("");
}

function bindToggles() {
  treeEl.querySelectorAll("[data-toggle]").forEach((row) => {
    row.addEventListener("click", () => {
      const node = row.closest(".node");
      const children = node.querySelector(":scope > .children");
      const toggle = row.querySelector(".toggle");
      if (!children) return;
      children.classList.toggle("collapsed");
      toggle.textContent = children.classList.contains("collapsed") ? "▶" : "▼";
    });
  });
}

async function loadProjects() {
  const res = await fetch("/api/projects");
  const projects = await res.json();
  projectSelect.innerHTML = projects
    .map((p) => `<option value="${p}">${p}</option>`)
    .join("");
  const params = new URLSearchParams(location.search);
  const q = params.get("project");
  if (q && projects.includes(q)) projectSelect.value = q;
  else if (projects.length) projectSelect.value = projects[0];
}

async function loadTree(project) {
  treeEl.innerHTML = '<p class="meta" style="padding:1rem">Loading…</p>';
  const res = await fetch(`/api/tree/${encodeURIComponent(project)}`);
  if (!res.ok) {
    treeEl.innerHTML = `<p class="error">Could not load tree for "${project}".</p>`;
    return;
  }
  const data = await res.json();
  titleEl.textContent = data.project || project;
  const composed = data.composed ? " · composed" : "";
  const err = data.compose_error ? ` · ERROR: ${data.compose_error}` : "";
  metaEl.textContent = `Updated ${data.updated || "—"}${composed}${err}`;
  renderConstraints(data.constraints);
  pendingBanner.classList.toggle("hidden", !data.pending);
  const roots = data.nodes || [];
  treeEl.innerHTML = roots.map((n) => renderNode(n)).join("");
  bindToggles();
  history.replaceState(null, "", `?project=${encodeURIComponent(project)}`);
}

async function init() {
  await loadProjects();
  const project = projectSelect.value;
  if (project) await loadTree(project);
  projectSelect.addEventListener("change", () => loadTree(projectSelect.value));
  refreshBtn.addEventListener("click", () => loadTree(projectSelect.value));
}

init().catch((err) => {
  treeEl.innerHTML = `<p class="error">${err.message}</p>`;
});
