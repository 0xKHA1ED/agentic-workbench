// AI Workflow Cockpit — Reactive Frontend & Vim-Speed Keyboard Triage Engine

// 1. STATE MANAGEMENT
const state = {
  currentProject: null,
  treeData: null,
  flatNodes: [], // Visually ordered, visible nodes
  selectedNodeId: null,
  selectedNodeIndex: -1,
  proposals: [],
  selectedProposalIndex: -1,
  claimsData: null, // { project, node_id, goal, claims: [...] }
  selectedClaimIndex: -1,
  filterMode: "all", // "all" | "weak" | "stale" | "strong"
  searchQuery: "",
  sseSource: null,
  collapsedNodeIds: new Set(),
};

// 2. UTILITY & HTML ESCAPING
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatValue(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object" && v !== null) return JSON.stringify(v);
  return String(v);
}

function renderData(data) {
  if (!data || typeof data !== "object") return "";
  return Object.entries(data)
    .filter(([k]) => k !== "claims") // Claims rendered in dedicated triage card
    .map(
      ([k, v]) =>
        `<span class="data-tag"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(formatValue(v))}</span>`
    )
    .join("");
}

function collectAllNodes(nodes) {
  const list = [];
  function walk(n) {
    list.push(n);
    if (n.children && Array.isArray(n.children)) {
      n.children.forEach(walk);
    }
  }
  (nodes || []).forEach(walk);
  return list;
}

function findNodeById(nodes, id) {
  if (!nodes || !Array.isArray(nodes) || !id) return null;
  for (const n of nodes) {
    if (n.id === id) return n;
    if (n.children && n.children.length > 0) {
      const found = findNodeById(n.children, id);
      if (found) return found;
    }
  }
  return null;
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

// 3. ACTIVITY CONSOLE STREAM
function logActivity(message, type = "info") {
  const consoleOutput = document.getElementById("console-output");
  if (!consoleOutput) return;

  const now = new Date();
  const timeStr = now.toTimeString().split(" ")[0]; // HH:MM:SS
  const line = document.createElement("div");
  line.className = `console-line ${type}`;
  line.innerHTML = `<span class="console-time">[${timeStr}]</span> ${escapeHtml(message)}`;
  consoleOutput.appendChild(line);

  // Retain maximum 200 console lines to manage memory
  while (consoleOutput.children.length > 200) {
    consoleOutput.removeChild(consoleOutput.firstChild);
  }
  consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// 4. HEALTH METER & CONSTRAINTS
function updateHealthMeter(allNodes) {
  const healthLabel = document.getElementById("health-label");
  const healthFill = document.getElementById("health-bar-fill");
  if (!healthLabel || !healthFill) return;

  if (!allNodes || allNodes.length === 0) {
    healthLabel.textContent = "Health: --%";
    healthFill.style.width = "0%";
    return;
  }

  const strongCount = allNodes.filter(
    (n) => n.status === "strong" || n.status === "verified_strong"
  ).length;
  const pct = Math.round((strongCount / allNodes.length) * 100);
  healthLabel.textContent = `Health: ${pct}%`;
  healthFill.style.width = `${pct}%`;
}

function renderConstraints(constraints) {
  const constraintsEl = document.getElementById("constraints");
  if (!constraintsEl) return;
  if (!constraints || Object.keys(constraints).length === 0) {
    constraintsEl.innerHTML = '<span class="empty-hint">None</span>';
    return;
  }
  constraintsEl.innerHTML = Object.entries(constraints)
    .map(
      ([k, v]) =>
        `<span class="chip"><span class="chip-muted">${escapeHtml(k)}</span> ${escapeHtml(formatValue(v))}</span>`
    )
    .join("");
}

// 5. INSTANT SEARCH & FILTERING LOGIC
function nodeMatchesDirectly(node, query, filterMode) {
  let matchesFilter = true;
  if (filterMode === "weak") {
    matchesFilter = node.status === "weak";
  } else if (filterMode === "stale") {
    matchesFilter = Boolean(node.stale) || node.status === "stale";
  } else if (filterMode === "strong") {
    matchesFilter = node.status === "strong" || node.status === "verified_strong";
  }

  if (!matchesFilter) return false;
  if (!query) return true;

  const searchable = [
    node.title || "",
    node.id || "",
    node.kind || "",
    node.status || "",
    node.notes || "",
    node.data?.pattern || "",
    node.data?.pain || "",
  ]
    .join(" ")
    .toLowerCase();

  return searchable.includes(query);
}

function filterNodeRecursive(node, query, filterMode, isFiltering) {
  const directMatch = nodeMatchesDirectly(node, query, filterMode);
  let childMatches = false;
  const filteredChildren = [];

  if (node.children && Array.isArray(node.children)) {
    for (const child of node.children) {
      const childRes = filterNodeRecursive(child, query, filterMode, isFiltering);
      if (childRes.visible) {
        childMatches = true;
        filteredChildren.push(childRes);
      }
    }
  }

  const visible = directMatch || childMatches;
  return {
    ...node,
    directMatch,
    hasMatchingDescendant: childMatches,
    visible,
    children: isFiltering ? filteredChildren : (node.children || []),
  };
}

function setFilter(mode) {
  state.filterMode = mode;
  document.querySelectorAll(".filter-chip").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-filter") === mode);
  });
  renderTree();
}

// 6. TREE HIERARCHY RENDERING
function renderTreeNodeHtml(node, depth = 0, isFiltering = false) {
  const children = node.children || [];
  const hasChildren = children.length > 0;
  const isCollapsed = !isFiltering && state.collapsedNodeIds.has(node.id);
  const isSelected = state.selectedNodeId === node.id;
  const stale = node.stale ? " stale" : "";
  const weak = node.status === "weak" ? " node-weak" : "";
  const status = node.status || "empty";
  const statusClass = `badge-status-${status.replace(/-/g, "_")}`;

  const childHtml = hasChildren
    ? `<div class="children${isCollapsed ? " collapsed" : ""}">${children
        .map((c) => renderTreeNodeHtml(c, depth + 1, isFiltering))
        .join("")}</div>`
    : "";

  const title = escapeHtml(node.title || node.id);
  const nodeId = escapeHtml(node.id);
  const kind = escapeHtml(node.kind || "?");

  return `
    <div class="node${stale}${weak}${isSelected ? " selected" : ""}" data-node-id="${nodeId}" data-depth="${depth}">
      <div class="node-row${isSelected ? " selected" : ""}" data-status="${escapeHtml(status)}">
        <span class="toggle${hasChildren ? "" : " empty"}" data-toggle-btn>${hasChildren ? (isCollapsed ? "▶" : "▼") : ""}</span>
        <div class="node-body">
          <div class="node-title-line">
            <span class="node-title">${title}</span>
            <span class="node-id">${nodeId}</span>
            <span class="badge badge-kind">${kind}</span>
            <span class="badge ${statusClass}">${escapeHtml(status)}</span>
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

function bindTreeEvents() {
  const treeEl = document.getElementById("tree");
  if (!treeEl) return;

  const rows = treeEl.querySelectorAll(".node-row");
  rows.forEach((row) => {
    const nodeEl = row.closest(".node");
    const nodeId = nodeEl.getAttribute("data-node-id");

    row.addEventListener("click", (e) => {
      // Toggle button clicked
      if (e.target.hasAttribute("data-toggle-btn") || e.target.classList.contains("toggle")) {
        const node = findNodeById(state.treeData?.nodes, nodeId);
        if (node && node.children && node.children.length > 0) {
          if (state.collapsedNodeIds.has(nodeId)) {
            state.collapsedNodeIds.delete(nodeId);
          } else {
            state.collapsedNodeIds.add(nodeId);
          }
          renderTree();
        }
        return;
      }

      // Node row selected
      selectNode(nodeId, "first");
    });
  });
}

function renderTree() {
  const treeEl = document.getElementById("tree");
  if (!treeEl) return;

  const roots = state.treeData?.nodes || [];
  const query = state.searchQuery;
  const filterMode = state.filterMode;
  const isFiltering = Boolean(query) || filterMode !== "all";

  // Filter tree hierarchy
  const processedRoots = [];
  for (const root of roots) {
    const processed = filterNodeRecursive(root, query, filterMode, isFiltering);
    if (processed.visible) {
      processedRoots.push(processed);
    }
  }

  // Build visually visible flatNodes list
  state.flatNodes = [];
  function collectVisibleFlat(node) {
    state.flatNodes.push(node);
    const hasChildren = node.children && node.children.length > 0;
    const isCollapsed = !isFiltering && state.collapsedNodeIds.has(node.id);
    if (hasChildren && !isCollapsed) {
      node.children.forEach(collectVisibleFlat);
    }
  }
  processedRoots.forEach(collectVisibleFlat);

  // Update stats
  const allNodes = collectAllNodes(roots);
  const statsEl = document.getElementById("tree-stats");
  if (statsEl) {
    if (isFiltering) {
      statsEl.textContent = `${state.flatNodes.length} / ${allNodes.length} nodes`;
    } else {
      statsEl.textContent = `${allNodes.length} node${allNodes.length === 1 ? "" : "s"}`;
    }
  }

  if (processedRoots.length === 0) {
    treeEl.innerHTML = '<p class="empty-hint" style="padding:1rem">No nodes match the current filter/search criteria.</p>';
    return;
  }

  treeEl.innerHTML = processedRoots.map((n) => renderTreeNodeHtml(n, 0, isFiltering)).join("");
  bindTreeEvents();

  state.selectedNodeIndex = state.flatNodes.findIndex((n) => n.id === state.selectedNodeId);
}

// 7. NODE INSPECTION & SELECTION
async function selectNode(nodeId, claimFocus = "first") {
  state.selectedNodeId = nodeId;
  state.selectedNodeIndex = state.flatNodes.findIndex((n) => n.id === nodeId);

  // Update visual selection
  document.querySelectorAll("#tree .node").forEach((el) => {
    const isThis = el.getAttribute("data-node-id") === nodeId;
    el.classList.toggle("selected", isThis);
    const row = el.querySelector(":scope > .node-row");
    if (row) row.classList.toggle("selected", isThis);
  });

  const selectedRow = document.querySelector(`#tree .node[data-node-id="${nodeId}"] > .node-row`);
  if (selectedRow) {
    selectedRow.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  const node = findNodeById(state.treeData?.nodes, nodeId);
  if (node) {
    renderNodeDetails(node);
  }

  if (state.currentProject) {
    await loadNodeHud(state.currentProject, nodeId);
    await loadClaims(state.currentProject, nodeId, claimFocus);
  }
}

// Epic A/C — unified Node HUD: one read-only glance at a node's loop position.
async function loadNodeHud(project, nodeId) {
  const hud = document.getElementById("node-hud");
  if (!hud) return;
  try {
    const res = await fetch(
      `/api/node/${encodeURIComponent(project)}/${encodeURIComponent(nodeId)}`
    );
    if (!res.ok) {
      hud.innerHTML = `<span class="node-hud-empty">No status for "${escapeHtml(nodeId)}".</span>`;
      return;
    }
    renderNodeHud(await res.json());
  } catch (err) {
    hud.innerHTML = `<span class="node-hud-empty">HUD error: ${escapeHtml(String(err))}</span>`;
  }
}

function renderNodeHud(status) {
  const hud = document.getElementById("node-hud");
  if (!hud) return;
  const gates = status.gate_states || {};
  const claims = status.claims || {};
  const chip = (label, value, ok) =>
    `<span class="hud-chip ${ok ? "hud-ok" : "hud-warn"}">${escapeHtml(label)}: ${escapeHtml(String(value))}</span>`;
  const rows = [];
  rows.push(chip("contract", gates.contract_present ? "yes" : "no", !!gates.contract_present));
  rows.push(chip("verify", gates.verify_present ? "yes" : "no", !!gates.verify_present));
  rows.push(chip("analyze", gates.analyze_status || "missing", gates.analyze_status === "complete" || gates.analyze_status === "skipped"));
  rows.push(chip("checklist ✗", gates.checklist_unchecked ?? 0, (gates.checklist_unchecked ?? 0) === 0));
  rows.push(chip("clarify", gates.clarify_status || "—", gates.clarify_status === "complete" || gates.clarify_status === null || gates.clarify_status === undefined));
  rows.push(chip("spec_approved", gates.spec_approved ? "yes" : "no", !!gates.spec_approved));
  if (claims.exists) {
    rows.push(chip("claims", `${claims.approved}/${claims.total}`, claims.pending === 0));
  }
  if (status.children_summary) {
    const cs = status.children_summary;
    rows.push(chip("children", `${cs.strong}/${cs.total_leaves} strong`, cs.all_strong));
  }
  const links = [];
  if (status.contract) links.push(`<div class="hud-link">contract: ${escapeHtml(status.contract)}</div>`);
  if (status.verify_cmd) links.push(`<div class="hud-link">verify: <code>${escapeHtml(status.verify_cmd)}</code></div>`);
  if (status.dogfood) links.push(`<div class="hud-link">dogfood: ${escapeHtml(status.dogfood)}</div>`);
  hud.innerHTML = `<div class="hud-chips">${rows.join("")}</div>${links.join("")}`;
}

function renderNodeDetails(node) {
  document.getElementById("node-detail-title").textContent = node.title || node.id;
  document.getElementById("node-detail-id").textContent = node.id;

  const kindBadge = document.getElementById("node-detail-kind");
  if (kindBadge) kindBadge.textContent = node.kind || "—";

  const statusBadge = document.getElementById("node-detail-status");
  if (statusBadge) {
    const status = node.status || "empty";
    statusBadge.textContent = status;
    statusBadge.className = `badge badge-status-${status.replace(/-/g, "_")}`;
  }

  const patternEl = document.getElementById("node-detail-pattern");
  if (patternEl) patternEl.textContent = node.data?.pattern || "none";

  const painEl = document.getElementById("node-detail-pain");
  if (painEl) painEl.textContent = node.data?.pain || "none";

  const notesEl = document.getElementById("node-detail-notes");
  if (notesEl) notesEl.textContent = node.notes || "none";

  // Reset verify status for node
  const verifyStatus = document.getElementById("verify-status");
  if (verifyStatus) {
    verifyStatus.textContent = "idle";
    verifyStatus.className = "badge badge-status-empty";
  }
  const verifyOutput = document.getElementById("verify-output");
  if (verifyOutput) {
    verifyOutput.innerHTML = "<code>Ready to run verification.</code>";
  }
}

function toggleSelectedNodeExpansion() {
  if (!state.selectedNodeId) return;
  const node = findNodeById(state.treeData?.nodes, state.selectedNodeId);
  if (!node || !node.children || node.children.length === 0) return;

  if (state.collapsedNodeIds.has(node.id)) {
    state.collapsedNodeIds.delete(node.id);
  } else {
    state.collapsedNodeIds.add(node.id);
  }
  renderTree();
}

// 8. CLAIMS TRIAGE
async function loadClaims(project, nodeId, claimFocus = "first") {
  try {
    const res = await fetch(`/api/claims/${encodeURIComponent(project)}/${encodeURIComponent(nodeId)}`);
    if (!res.ok) {
      state.claimsData = { project, node_id: nodeId, claims: [] };
      state.selectedClaimIndex = -1;
      renderClaims();
      return;
    }

    const data = await res.json();
    state.claimsData = data;
    const claims = data.claims || [];

    if (claims.length > 0) {
      if (claimFocus === "last") {
        state.selectedClaimIndex = claims.length - 1;
      } else if (
        claimFocus === "keep" &&
        state.selectedClaimIndex >= 0 &&
        state.selectedClaimIndex < claims.length
      ) {
        // Keep current selection
      } else {
        const firstPending = claims.findIndex((c) => c.decision === "pending" || !c.decision);
        state.selectedClaimIndex = firstPending >= 0 ? firstPending : 0;
      }
    } else {
      state.selectedClaimIndex = -1;
    }

    renderClaims();
  } catch (err) {
    state.claimsData = { project, node_id: nodeId, claims: [] };
    state.selectedClaimIndex = -1;
    renderClaims();
  }
}

function renderClaims() {
  const claimsCountEl = document.getElementById("claims-count");
  const claimsGoalText = document.getElementById("claims-goal-text");
  const claimsListEl = document.getElementById("claims-list");
  if (!claimsCountEl || !claimsGoalText || !claimsListEl) return;

  const claims = state.claimsData?.claims || [];
  claimsCountEl.textContent = `${claims.length} claim${claims.length === 1 ? "" : "s"}`;

  if (state.claimsData?.goal) {
    claimsGoalText.textContent = state.claimsData.goal;
  } else if (claims.length > 0) {
    claimsGoalText.textContent = `Verification claims for node "${state.selectedNodeId}"`;
  } else {
    claimsGoalText.textContent = state.selectedNodeId
      ? `No active claims for node "${state.selectedNodeId}".`
      : "No active claim set loaded.";
  }

  if (claims.length === 0) {
    claimsListEl.innerHTML =
      '<p class="empty-hint">No claims for this node. Stage claims via workflow_stage_contract_claims.</p>';
    return;
  }

  claimsListEl.innerHTML = claims
    .map((claim, idx) => {
      const isSelected = idx === state.selectedClaimIndex;
      const decision = claim.decision || "pending";
      let badgeClass = "badge badge-status-stale";
      let itemDecisionClass = "";

      if (decision === "approved") {
        badgeClass = "badge badge-status-verified_strong";
        itemDecisionClass = " approved";
      } else if (decision === "rejected") {
        badgeClass = "badge badge-status-weak";
        itemDecisionClass = " rejected";
      } else if (decision === "skipped") {
        badgeClass = "badge badge-status-empty";
        itemDecisionClass = " skipped";
      }

      const execHtml = claim.execution
        ? `<div class="claim-execution">${escapeHtml(claim.execution)}</div>`
        : "";

      return `
        <div class="claim-item${itemDecisionClass}${isSelected ? " selected" : ""}" data-claim-id="${escapeHtml(claim.id)}" data-claim-index="${idx}">
          <div class="claim-body">
            <div class="claim-id">${escapeHtml(claim.id)} · ${escapeHtml(claim.kind || "contract")}</div>
            <div class="claim-text">${escapeHtml(claim.text || "")}</div>
            ${execHtml}
          </div>
          <span class="claim-decision-badge ${badgeClass}">${escapeHtml(decision)}</span>
        </div>
      `;
    })
    .join("");

  // Bind click handlers on claims
  claimsListEl.querySelectorAll(".claim-item").forEach((el) => {
    el.addEventListener("click", () => {
      const idx = Number(el.getAttribute("data-claim-index"));
      state.selectedClaimIndex = idx;
      renderClaims();
    });
  });

  const activeClaimEl = claimsListEl.querySelector(
    `.claim-item[data-claim-index="${state.selectedClaimIndex}"]`
  );
  if (activeClaimEl) {
    activeClaimEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

async function triageClaim(project, nodeId, claimId, decision) {
  try {
    const res = await fetch("/api/claims/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project,
        node_id: nodeId,
        claim_id: claimId,
        decision,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    const data = await res.json();
    state.claimsData = data;
    renderClaims();

    const logType =
      decision === "approved" ? "success" : decision === "rejected" ? "warn" : "info";
    logActivity(`Claim "${claimId}" marked ${decision.toUpperCase()} on node "${nodeId}".`, logType);
  } catch (err) {
    logActivity(`Failed to triage claim "${claimId}": ${err.message}`, "error");
  }
}

async function approveAllClaims() {
  if (!state.claimsData || !state.claimsData.claims || state.claimsData.claims.length === 0) {
    logActivity("No claims to approve on active node.", "warn");
    return;
  }
  const pendingClaims = state.claimsData.claims.filter((c) => c.decision !== "approved");
  if (pendingClaims.length === 0) {
    logActivity("All claims on this node are already approved.", "info");
    return;
  }

  const nodeId = state.selectedNodeId;
  const project = state.currentProject;
  logActivity(`Batch approving ${pendingClaims.length} claims for node "${nodeId}"...`, "info");

  for (const claim of pendingClaims) {
    try {
      await postJson("/api/claims/triage", {
        project,
        node_id: nodeId,
        claim_id: claim.id,
        decision: "approved",
      });
      claim.decision = "approved";
      claim.triaged_at = new Date().toISOString();
    } catch (err) {
      logActivity(`Failed approving claim ${claim.id}: ${err.message}`, "error");
    }
  }

  renderClaims();
  logActivity(`Successfully approved all claims on node "${nodeId}".`, "success");
}

// 9. PROPOSALS BANNER & DIFF ENGINE
function formatDiff(diffText) {
  if (!diffText) return "<code>No diff available.</code>";
  const lines = diffText.split("\n");
  const formatted = lines
    .map((line) => {
      const esc = escapeHtml(line);
      if (line.startsWith("+++") || line.startsWith("---")) {
        return `<span class="diff-line-hunk">${esc}</span>`;
      } else if (line.startsWith("+")) {
        return `<span class="diff-line-add">${esc}</span>`;
      } else if (line.startsWith("-")) {
        return `<span class="diff-line-del">${esc}</span>`;
      } else if (line.startsWith("@@")) {
        return `<span class="diff-line-hunk">${esc}</span>`;
      }
      return `<span>${esc}</span>`;
    })
    .join("\n");
  return `<code>${formatted}</code>`;
}

async function loadProposals(project) {
  try {
    const res = await fetch(`/api/proposals/${encodeURIComponent(project)}`);
    if (!res.ok) {
      state.proposals = [];
      renderProposals();
      return;
    }
    const data = await res.json();
    state.proposals = data.proposals || [];
    if (state.selectedProposalIndex >= state.proposals.length || state.selectedProposalIndex < 0) {
      state.selectedProposalIndex = state.proposals.length > 0 ? 0 : -1;
    }
    renderProposals();
  } catch (err) {
    state.proposals = [];
    renderProposals();
  }
}

function renderProposals() {
  const banner = document.getElementById("proposals-banner");
  const countEl = document.getElementById("proposals-count");
  const listEl = document.getElementById("proposals-list");
  const diffEl = document.getElementById("proposal-diff");
  const pendingBanner = document.getElementById("pending-banner");
  if (!banner || !countEl || !listEl || !diffEl) return;

  const count = state.proposals.length;
  countEl.textContent = String(count);

  if (count === 0) {
    banner.classList.add("hidden");
    if (pendingBanner) pendingBanner.classList.add("hidden");
    listEl.innerHTML = "";
    diffEl.innerHTML = "<code>No pending proposals.</code>";
    return;
  }

  banner.classList.remove("hidden");
  if (pendingBanner) pendingBanner.classList.add("hidden");

  if (count > 1) {
    listEl.innerHTML = state.proposals
      .map(
        (p, idx) => `
        <button type="button" class="btn ${
          idx === state.selectedProposalIndex ? "btn-primary" : "btn-approve-all"
        }" data-prop-index="${idx}">
          ${escapeHtml(p.target)}
        </button>
      `
      )
      .join(" ");

    listEl.querySelectorAll("[data-prop-index]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.selectedProposalIndex = Number(btn.getAttribute("data-prop-index"));
        renderProposals();
      });
    });
  } else {
    listEl.innerHTML = "";
  }

  const activeProp = state.proposals[state.selectedProposalIndex] || state.proposals[0];
  if (activeProp && activeProp.diff) {
    diffEl.innerHTML = formatDiff(activeProp.diff);
  } else {
    diffEl.innerHTML = "<code>No diff available.</code>";
  }
}

async function applyProposal(fragment) {
  if (!state.currentProject) return;
  const prop = state.proposals[state.selectedProposalIndex] || state.proposals[0];
  const targetLabel = prop ? prop.target : "proposal";

  try {
    logActivity(`Applying proposal for ${targetLabel}...`, "info");
    await postJson("/api/proposals/apply", {
      project: state.currentProject,
      fragment: fragment !== undefined ? fragment : prop ? prop.fragment : null,
    });
    logActivity(`Proposal for ${targetLabel} applied successfully.`, "success");
    await loadTree(state.currentProject, true);
    await loadProposals(state.currentProject);
  } catch (err) {
    logActivity(`Failed to apply proposal for ${targetLabel}: ${err.message}`, "error");
  }
}

async function rejectProposal(fragment) {
  if (!state.currentProject) return;
  const prop = state.proposals[state.selectedProposalIndex] || state.proposals[0];
  const targetLabel = prop ? prop.target : "proposal";

  try {
    logActivity(`Rejecting proposal for ${targetLabel}...`, "warn");
    await postJson("/api/proposals/reject", {
      project: state.currentProject,
      fragment: fragment !== undefined ? fragment : prop ? prop.fragment : null,
    });
    logActivity(`Proposal for ${targetLabel} rejected.`, "warn");
    await loadTree(state.currentProject, true);
    await loadProposals(state.currentProject);
  } catch (err) {
    logActivity(`Failed to reject proposal for ${targetLabel}: ${err.message}`, "error");
  }
}

// 10. DECAY SCAN WIDGET
async function runDecayScan() {
  if (!state.currentProject) {
    logActivity("Please select a project before scanning for decay.", "warn");
    return;
  }

  const project = state.currentProject;
  const scanBtn = document.getElementById("btn-scan-decay");
  if (scanBtn) scanBtn.disabled = true;
  logActivity(`[decay] Starting decay scan for project "${project}"...`, "info");

  try {
    const res = await fetch("/api/decay-scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, dry_run: false }),
    });
    const data = await res.json();

    if (!res.ok) {
      logActivity(
        `[decay] Scan error for "${project}": ${data.error || res.statusText}`,
        "error"
      );
      return;
    }

    const scanned = data.scanned != null ? data.scanned : 0;
    const decayed = data.decayed != null ? data.decayed : 0;
    const refreshed = data.refreshed != null ? data.refreshed : 0;
    logActivity(
      `[decay] Project "${project}": scanned ${scanned}, decayed ${decayed}, refreshed ${refreshed}`,
      decayed > 0 ? "warn" : "success"
    );
    await loadTree(project, true);
  } catch (err) {
    logActivity(`[decay] Decay scan execution error for "${project}": ${err.message}`, "error");
  } finally {
    if (scanBtn) scanBtn.disabled = false;
  }
}

// 11. VERIFICATION RUNNER WIDGET
async function runVerification() {
  if (!state.currentProject || !state.selectedNodeId) {
    logActivity("Please select a tree node before running verification.", "warn");
    return;
  }

  const nodeId = state.selectedNodeId;
  const project = state.currentProject;
  const verifyBtn = document.getElementById("btn-run-verify");
  const verifyStatus = document.getElementById("verify-status");
  const verifyOutput = document.getElementById("verify-output");

  if (verifyBtn) verifyBtn.disabled = true;
  if (verifyStatus) {
    verifyStatus.textContent = "running";
    verifyStatus.className = "badge badge-status-stale";
  }
  if (verifyOutput) {
    verifyOutput.innerHTML = `<code>Running verification for node "${escapeHtml(nodeId)}"...</code>`;
  }
  logActivity(`[verify] Starting verification for node "${nodeId}"...`, "info");

  try {
    const res = await fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, node_id: nodeId }),
    });
    const data = await res.json();

    if (!res.ok) {
      if (verifyStatus) {
        verifyStatus.textContent = "failed";
        verifyStatus.className = "badge badge-status-weak";
      }
      if (verifyOutput) {
        verifyOutput.innerHTML = `<code>Error: ${escapeHtml(data.error || "Verification failed")}</code>`;
      }
      logActivity(
        `[verify] Verification error for node "${nodeId}": ${data.error || res.statusText}`,
        "error"
      );
      return;
    }

    const isPassed = data.status === "passed";
    if (verifyStatus) {
      verifyStatus.textContent = isPassed ? "passed" : "failed";
      verifyStatus.className = `badge ${isPassed ? "badge-status-verified_strong" : "badge-status-weak"}`;
    }

    const stdout = data.stdout ? escapeHtml(data.stdout) : "(none)";
    const stderr = data.stderr ? escapeHtml(data.stderr) : "(none)";
    const duration = data.duration_sec != null ? `${Number(data.duration_sec).toFixed(3)}s` : "—";
    const exitCode = data.exit_code != null ? data.exit_code : "—";
    const command = data.command ? escapeHtml(data.command) : "—";

    if (verifyOutput) {
      verifyOutput.innerHTML = `<code>Command:   ${command}
Status:    ${data.status} (exit ${exitCode}, duration: ${duration})

--- STDOUT ---
${stdout}

--- STDERR ---
${stderr}</code>`;
    }

    const logType = isPassed ? "success" : "error";
    logActivity(
      `[verify] Node "${nodeId}": ${data.status.toUpperCase()} (exit ${exitCode}, duration: ${duration})`,
      logType
    );

    // Refresh tree to reflect any status change
    await loadTree(project, true);
  } catch (err) {
    if (verifyStatus) {
      verifyStatus.textContent = "error";
      verifyStatus.className = "badge badge-status-weak";
    }
    if (verifyOutput) {
      verifyOutput.innerHTML = `<code>Error executing verification: ${escapeHtml(err.message)}</code>`;
    }
    logActivity(`[verify] Verification execution error for "${nodeId}": ${err.message}`, "error");
  } finally {
    if (verifyBtn) verifyBtn.disabled = false;
  }
}

// 12. REAL-TIME SSE STREAM
function connectSSE(project) {
  if (state.sseSource) {
    state.sseSource.close();
    state.sseSource = null;
  }

  const sseStatus = document.getElementById("sse-status");
  if (sseStatus) {
    sseStatus.className = "status-dot connecting";
    sseStatus.title = "Connection: Connecting...";
  }

  try {
    const sse = new EventSource(`/api/events/${encodeURIComponent(project)}`);
    state.sseSource = sse;

    sse.addEventListener("connected", () => {
      if (sseStatus) {
        sseStatus.className = "status-dot connected";
        sseStatus.title = "Connection: Connected";
      }
      logActivity(`[SSE] Connected to event stream for "${project}"`, "event");
    });

    sse.addEventListener("tree_changed", async () => {
      logActivity(`[SSE] Detected file changes on "${project}". Refreshing view...`, "event");
      await loadTree(project, true);
      await loadProposals(project);
      if (state.selectedNodeId) {
        await loadClaims(project, state.selectedNodeId, "keep");
      }
    });

    sse.addEventListener("ping", () => {
      if (sseStatus && !sseStatus.classList.contains("connected")) {
        sseStatus.className = "status-dot connected";
        sseStatus.title = "Connection: Connected";
      }
    });

    sse.onerror = () => {
      if (sseStatus) {
        if (sse.readyState === EventSource.CONNECTING) {
          sseStatus.className = "status-dot connecting";
          sseStatus.title = "Connection: Reconnecting...";
        } else {
          sseStatus.className = "status-dot disconnected";
          sseStatus.title = "Connection: Disconnected";
        }
      }
    };
  } catch (err) {
    if (sseStatus) {
      sseStatus.className = "status-dot disconnected";
      sseStatus.title = "Connection: Disconnected";
    }
    logActivity(`[SSE] Failed to establish EventSource: ${err.message}`, "error");
  }
}

// 12. VIM-SPEED KEYBOARD TRIAGE & NAVIGATION
function advanceSelection(delta) {
  const claims = state.claimsData?.claims || [];

  // 1. Move within active claims if present
  if (claims.length > 0 && state.selectedClaimIndex >= 0) {
    const nextClaimIndex = state.selectedClaimIndex + delta;
    if (nextClaimIndex >= 0 && nextClaimIndex < claims.length) {
      state.selectedClaimIndex = nextClaimIndex;
      renderClaims();
      return;
    }
  }

  // 2. Move between tree nodes
  if (state.flatNodes.length === 0) return;

  if (state.selectedNodeIndex === -1) {
    const idx = delta > 0 ? 0 : state.flatNodes.length - 1;
    const targetNode = state.flatNodes[idx];
    if (targetNode) {
      selectNode(targetNode.id, delta < 0 ? "last" : "first");
    }
    return;
  }

  // Prevent re-selecting boundary node and resetting claim selection
  if (delta > 0 && state.selectedNodeIndex >= state.flatNodes.length - 1) {
    return;
  }
  if (delta < 0 && state.selectedNodeIndex <= 0) {
    return;
  }

  const nextNodeIndex = state.selectedNodeIndex + delta;
  if (nextNodeIndex >= 0 && nextNodeIndex < state.flatNodes.length) {
    const targetNode = state.flatNodes[nextNodeIndex];
    if (targetNode) {
      selectNode(targetNode.id, delta < 0 ? "last" : "first");
    }
  }
}

async function handleApprove() {
  // If active claim is selected, triage claim
  if (
    state.claimsData &&
    state.claimsData.claims &&
    state.claimsData.claims.length > 0 &&
    state.selectedClaimIndex >= 0
  ) {
    const claim = state.claimsData.claims[state.selectedClaimIndex];
    if (claim) {
      await triageClaim(state.currentProject, state.selectedNodeId, claim.id, "approved");
      // Advance to next claim or next node
      if (state.selectedClaimIndex < state.claimsData.claims.length - 1) {
        state.selectedClaimIndex++;
        renderClaims();
      } else {
        advanceSelection(1);
      }
      return;
    }
  }

  // If no claims selected, triage active proposal
  if (state.proposals && state.proposals.length > 0) {
    const propIndex = state.selectedProposalIndex >= 0 ? state.selectedProposalIndex : 0;
    const prop = state.proposals[propIndex];
    if (prop) {
      await applyProposal(prop.fragment);
    }
  }
}

async function handleReject() {
  // If active claim is selected, triage claim
  if (
    state.claimsData &&
    state.claimsData.claims &&
    state.claimsData.claims.length > 0 &&
    state.selectedClaimIndex >= 0
  ) {
    const claim = state.claimsData.claims[state.selectedClaimIndex];
    if (claim) {
      await triageClaim(state.currentProject, state.selectedNodeId, claim.id, "rejected");
      // Advance to next claim or next node
      if (state.selectedClaimIndex < state.claimsData.claims.length - 1) {
        state.selectedClaimIndex++;
        renderClaims();
      } else {
        advanceSelection(1);
      }
      return;
    }
  }

  // If no claims selected, triage active proposal
  if (state.proposals && state.proposals.length > 0) {
    const propIndex = state.selectedProposalIndex >= 0 ? state.selectedProposalIndex : 0;
    const prop = state.proposals[propIndex];
    if (prop) {
      await rejectProposal(prop.fragment);
    }
  }
}

function openModal() {
  const modal = document.getElementById("shortcuts-modal");
  if (modal) modal.classList.remove("hidden");
}

function closeModal() {
  const modal = document.getElementById("shortcuts-modal");
  if (modal) modal.classList.add("hidden");
}

function toggleModal() {
  const modal = document.getElementById("shortcuts-modal");
  if (modal) modal.classList.toggle("hidden");
}

function bindKeyboardShortcuts() {
  window.addEventListener("keydown", (e) => {
    const tag = e.target.tagName ? e.target.tagName.toLowerCase() : "";
    const isInput = tag === "input" || tag === "textarea" || tag === "select";

    if (isInput) {
      if (e.key === "Escape") {
        e.target.blur();
      }
      return;
    }

    if (e.key === "Escape") {
      closeModal();
      return;
    }

    if (e.key === "?") {
      e.preventDefault();
      toggleModal();
      return;
    }

    if (e.key === "/") {
      e.preventDefault();
      const searchInput = document.getElementById("search-input");
      if (searchInput) searchInput.focus();
      return;
    }

    if (e.key === "r" || e.key === "R") {
      e.preventDefault();
      if (state.currentProject) {
        loadTree(state.currentProject, true);
        loadProposals(state.currentProject);
        logActivity("Refreshed project tree and proposals.", "info");
      }
      return;
    }

    if (e.key === "j" || e.key === "J" || e.key === "ArrowDown") {
      e.preventDefault();
      advanceSelection(1);
      return;
    }

    if (e.key === "k" || e.key === "K" || e.key === "ArrowUp") {
      e.preventDefault();
      advanceSelection(-1);
      return;
    }

    if (e.key === "y" || e.key === "Y") {
      e.preventDefault();
      handleApprove();
      return;
    }

    if (e.key === "n" || e.key === "N") {
      e.preventDefault();
      handleReject();
      return;
    }

    if (e.key === "a" || e.key === "A") {
      e.preventDefault();
      approveAllClaims();
      return;
    }

    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      toggleSelectedNodeExpansion();
      return;
    }
  });
}

// 13. REST API CLIENT & INITIALIZATION
async function loadTree(project, preserveSelection = false) {
  const treeEl = document.getElementById("tree");
  const currentSelectedId = preserveSelection ? state.selectedNodeId : null;

  const res = await fetch(`/api/tree/${encodeURIComponent(project)}`);
  if (!res.ok) {
    if (treeEl) {
      treeEl.innerHTML = `<p class="error">Could not load tree for "${escapeHtml(project)}".</p>`;
    }
    return;
  }

  const data = await res.json();
  state.treeData = data;

  const titleEl = document.getElementById("project-title");
  if (titleEl) titleEl.textContent = data.project || project;

  const composed = data.composed ? " · composed" : "";
  const err = data.compose_error ? ` · ERROR: ${data.compose_error}` : "";
  const metaEl = document.getElementById("meta");
  if (metaEl) metaEl.textContent = `Updated ${data.updated || "—"}${composed}${err}`;

  renderConstraints(data.constraints);

  const allNodes = collectAllNodes(data.nodes);
  updateHealthMeter(allNodes);
  renderTree();

  if (currentSelectedId && findNodeById(data.nodes, currentSelectedId)) {
    selectNode(currentSelectedId, "keep");
  } else if (state.flatNodes.length > 0) {
    selectNode(state.flatNodes[0].id, "first");
  } else {
    state.selectedNodeId = null;
    state.selectedNodeIndex = -1;
  }
}

async function switchProject(project) {
  if (!project) return;
  state.currentProject = project;
  state.selectedNodeId = null;
  state.selectedNodeIndex = -1;
  state.claimsData = null;
  state.selectedClaimIndex = -1;
  state.collapsedNodeIds.clear();

  history.replaceState(null, "", `?project=${encodeURIComponent(project)}`);

  connectSSE(project);
  await loadTree(project);
  await loadProposals(project);
}

async function loadProjects() {
  const select = document.getElementById("project-select");
  const res = await fetch("/api/projects");
  if (!res.ok) throw new Error("Failed to load projects list");

  const projects = await res.json();
  if (select) {
    select.innerHTML = projects
      .map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`)
      .join("");

    const params = new URLSearchParams(location.search);
    const q = params.get("project");
    if (q && projects.includes(q)) {
      select.value = q;
    } else if (projects.length > 0) {
      select.value = projects[0];
    }
    return select.value;
  }
  return projects[0] || null;
}

function bindControls() {
  const projectSelect = document.getElementById("project-select");
  if (projectSelect) {
    projectSelect.addEventListener("change", () => switchProject(projectSelect.value));
  }

  const refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      if (state.currentProject) {
        loadTree(state.currentProject, true);
        loadProposals(state.currentProject);
        logActivity("Tree and proposals refreshed.", "info");
      }
    });
  }

  // Filter chips
  document.querySelectorAll(".filter-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      setFilter(btn.getAttribute("data-filter"));
    });
  });

  // Search input
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.searchQuery = searchInput.value.trim().toLowerCase();
      renderTree();
    });
    searchInput.addEventListener("search", () => {
      state.searchQuery = searchInput.value.trim().toLowerCase();
      renderTree();
    });
  }

  // Shortcuts modal
  const shortcutsBtn = document.getElementById("shortcuts-btn");
  if (shortcutsBtn) shortcutsBtn.addEventListener("click", toggleModal);

  const shortcutsCloseBtn = document.getElementById("shortcuts-close-btn");
  if (shortcutsCloseBtn) shortcutsCloseBtn.addEventListener("click", closeModal);

  const modalOverlay = document.getElementById("shortcuts-modal");
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });
  }

  // Proposal action buttons
  const applyPropBtn = document.getElementById("btn-apply-proposal");
  if (applyPropBtn) {
    applyPropBtn.addEventListener("click", () => {
      const prop = state.proposals[state.selectedProposalIndex];
      if (prop) applyProposal(prop.fragment);
    });
  }

  const rejectPropBtn = document.getElementById("btn-reject-proposal");
  if (rejectPropBtn) {
    rejectPropBtn.addEventListener("click", () => {
      const prop = state.proposals[state.selectedProposalIndex];
      if (prop) rejectProposal(prop.fragment);
    });
  }

  // Claims action buttons
  const approveClaimBtn = document.getElementById("btn-approve-claim");
  if (approveClaimBtn) approveClaimBtn.addEventListener("click", () => handleApprove());

  const rejectClaimBtn = document.getElementById("btn-reject-claim");
  if (rejectClaimBtn) rejectClaimBtn.addEventListener("click", () => handleReject());

  const approveAllBtn = document.getElementById("btn-approve-all");
  if (approveAllBtn) approveAllBtn.addEventListener("click", () => approveAllClaims());

  const scanDecayBtn = document.getElementById("btn-scan-decay");
  if (scanDecayBtn) scanDecayBtn.addEventListener("click", () => runDecayScan());

  // Verification button
  const runVerifyBtn = document.getElementById("btn-run-verify");
  if (runVerifyBtn) runVerifyBtn.addEventListener("click", () => runVerification());

  // Console clear button
  const clearConsoleBtn = document.getElementById("console-clear-btn");
  if (clearConsoleBtn) {
    clearConsoleBtn.addEventListener("click", () => {
      const out = document.getElementById("console-output");
      if (out) out.innerHTML = "";
    });
  }

  bindKeyboardShortcuts();
}

async function init() {
  bindControls();
  const project = await loadProjects();
  if (project) {
    await switchProject(project);
  }
}

init().catch((err) => {
  const treeEl = document.getElementById("tree");
  if (treeEl) treeEl.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
  logActivity(`Initialization error: ${err.message}`, "error");
});

