(() => {
  const STORAGE_KEY = "alphadesk.workspaceId";
  const META = {
    intelligence: ["Intelligence", "Material changes and saved intelligence cards."],
    portfolio: ["Portfolio", "Current book, coverage, and import workflow."],
    research: ["Research", "Private uploads that stay inside this workspace."],
    workbench: ["Workbench", "Run research, review durable runs, and create theses."],
    journal: ["Journal", "Decision journal and outcome reviews."],
    settings: ["Settings", "Workspace defaults and API connectivity."],
  };

  const els = {
    workspace: document.getElementById("workspace"),
    status: document.getElementById("status"),
    title: document.getElementById("view-title"),
    sub: document.getElementById("view-sub"),
    refresh: document.getElementById("refresh"),
    nav: document.getElementById("nav"),
  };

  let view = "intelligence";

  function workspaceId() {
    return (els.workspace.value || "ws_local").trim() || "ws_local";
  }

  function setStatus(message, kind = "") {
    els.status.textContent = message || "";
    els.status.className = `status ${kind}`.trim();
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("X-Workspace-Id", workspaceId());
    if (options.json !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    const res = await fetch(path, {
      ...options,
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ? JSON.stringify(body.detail) : detail;
      } catch (_) {
        /* ignore */
      }
      throw new Error(`${res.status}: ${detail}`);
    }
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function empty(message) {
    return `<div class="empty">${escapeHtml(message)}</div>`;
  }

  async function renderIntelligence() {
    const root = document.getElementById("view-intelligence");
    const cards = await api("/v1/cards?limit=50");
    if (!cards.length) {
      root.innerHTML = `<div class="panel">${empty("No intelligence cards yet. Monitoring will fill this surface later; you can also POST /v1/cards.")}</div>`;
      return;
    }
    root.innerHTML = `<div class="panel list">${cards
      .map(
        (c) => `<article class="row">
          <strong>${escapeHtml(c.title || c.id)}</strong>
          <div class="meta">${escapeHtml(c.symbol || "—")} · ${escapeHtml(c.card_type || "card")}</div>
          <div>${escapeHtml(c.headline || c.body || "")}</div>
        </article>`
      )
      .join("")}</div>`;
  }

  async function renderPortfolio() {
    const root = document.getElementById("view-portfolio");
    root.innerHTML = `<div class="stack">
      <div class="panel">
        <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Current book</h2>
        <div id="portfolio-summary" class="grid-3"></div>
        <div id="portfolio-table" style="margin-top:1rem;"></div>
      </div>
      <div class="panel">
        <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Import CSV</h2>
        <div class="form-row field">
          <label for="csv">Broker export</label>
          <textarea id="csv" placeholder="Paste CSV contents…"></textarea>
        </div>
        <div class="actions">
          <button type="button" class="btn-primary" id="import-confirm">Preview &amp; confirm import</button>
        </div>
        <div id="import-result" class="meta" style="margin-top:.75rem;"></div>
      </div>
    </div>`;

    const summaryEl = root.querySelector("#portfolio-summary");
    const tableEl = root.querySelector("#portfolio-table");
    try {
      const summary = await api("/v1/portfolios/current/summary");
      summaryEl.innerHTML = `
        <div class="stat"><div class="label">Positions</div><div class="value">${escapeHtml(summary.open_positions ?? "—")}</div></div>
        <div class="stat"><div class="label">Total value</div><div class="value">${escapeHtml(fmtMoney(summary.total_value))}</div></div>
        <div class="stat"><div class="label">Concentration</div><div class="value">${escapeHtml(fmtPct(summary.concentration))}</div></div>`;
    } catch (err) {
      summaryEl.innerHTML = empty(err.message.includes("404") ? "No current portfolio yet." : err.message);
    }

    try {
      const current = await api("/v1/portfolios/current");
      const positions = current.portfolio?.positions || current.positions || [];
      if (!positions.length) {
        tableEl.innerHTML = empty("Book is empty.");
      } else {
        tableEl.innerHTML = `<table class="table"><thead><tr><th>Symbol</th><th>Qty</th><th>Avg cost</th><th>Price</th></tr></thead><tbody>
          ${positions
            .map(
              (p) => `<tr>
                <td><strong>${escapeHtml(p.symbol)}</strong></td>
                <td>${escapeHtml(p.quantity)}</td>
                <td>${escapeHtml(p.avg_cost ?? p.average_cost ?? "—")}</td>
                <td>${escapeHtml(p.current_price ?? "—")}</td>
              </tr>`
            )
            .join("")}
        </tbody></table>`;
      }
    } catch (_) {
      tableEl.innerHTML = empty("Import a CSV to create the current book.");
    }

    root.querySelector("#import-confirm").onclick = async () => {
      const content = root.querySelector("#csv").value;
      const out = root.querySelector("#import-result");
      try {
        setStatus("Importing…");
        const preview = await api("/v1/portfolios/import/preview", {
          method: "POST",
          json: { content, as_of: new Date().toISOString().slice(0, 10) },
        });
        if (!preview.can_confirm) {
          out.textContent = `Preview blocked: ${(preview.errors || []).join("; ") || "fix columns"}`;
          setStatus("Import needs mapping", "error");
          return;
        }
        const confirmed = await api("/v1/portfolios/import/confirm", {
          method: "POST",
          json: { portfolio: preview.portfolio },
        });
        out.textContent = `Imported snapshot ${confirmed.id || "current"}.`;
        setStatus("Portfolio imported", "ok");
        await renderPortfolio();
      } catch (err) {
        out.textContent = err.message;
        setStatus(err.message, "error");
      }
    };
  }

  async function renderResearch() {
    const root = document.getElementById("view-research");
    root.innerHTML = `<div class="grid-2">
      <div class="panel">
        <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Upload</h2>
        <div class="form-row field"><label for="doc-title">Title</label><input id="doc-title" /></div>
        <div class="form-row field"><label for="doc-file">File (md / txt / csv / pdf)</label><input id="doc-file" type="file" /></div>
        <div class="actions"><button type="button" class="btn-primary" id="upload-doc">Upload private document</button></div>
      </div>
      <div class="panel">
        <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Search</h2>
        <div class="form-row field"><label for="doc-q">Query</label><input id="doc-q" placeholder="earnings, ACME…" /></div>
        <div class="actions"><button type="button" class="btn" id="search-doc">Search</button></div>
        <div id="search-hits" class="list" style="margin-top:.85rem;"></div>
      </div>
      <div class="panel" style="grid-column:1 / -1;">
        <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Library</h2>
        <div id="doc-list" class="list"></div>
      </div>
    </div>`;

    async function loadDocs() {
      const docs = await api("/v1/research/documents");
      const list = root.querySelector("#doc-list");
      if (!docs.length) {
        list.innerHTML = empty("No private documents in this workspace.");
        return;
      }
      list.innerHTML = docs
        .map(
          (d) => `<article class="row">
            <strong>${escapeHtml(d.title)}</strong>
            <div class="meta">${escapeHtml(d.filename)} · ${escapeHtml(d.kind)} · ${escapeHtml(d.size_bytes)} bytes</div>
            <div class="mono">${escapeHtml((d.extracted_text || "").slice(0, 220))}${(d.extracted_text || "").length > 220 ? "…" : ""}</div>
            <div class="actions"><button type="button" class="btn-danger" data-del="${escapeHtml(d.id)}">Delete</button></div>
          </article>`
        )
        .join("");
      list.querySelectorAll("[data-del]").forEach((btn) => {
        btn.onclick = async () => {
          await api(`/v1/research/documents/${btn.dataset.del}`, { method: "DELETE" });
          setStatus("Document deleted", "ok");
          await loadDocs();
        };
      });
    }

    root.querySelector("#upload-doc").onclick = async () => {
      const file = root.querySelector("#doc-file").files[0];
      if (!file) {
        setStatus("Choose a file first", "error");
        return;
      }
      const body = new FormData();
      body.append("file", file);
      const title = root.querySelector("#doc-title").value.trim();
      if (title) body.append("title", title);
      try {
        await api("/v1/research/documents", { method: "POST", body });
        setStatus("Uploaded", "ok");
        await loadDocs();
      } catch (err) {
        setStatus(err.message, "error");
      }
    };

    root.querySelector("#search-doc").onclick = async () => {
      const q = root.querySelector("#doc-q").value.trim();
      const hitsEl = root.querySelector("#search-hits");
      if (!q) return;
      const hits = await api(`/v1/research/search?q=${encodeURIComponent(q)}`);
      hitsEl.innerHTML = hits.length
        ? hits
            .map(
              (h) => `<article class="row"><strong>${escapeHtml(h.document.title)}</strong><div class="meta">${escapeHtml(h.snippet)}</div></article>`
            )
            .join("")
        : empty("No matches.");
    };

    await loadDocs();
  }

  async function renderWorkbench() {
    const root = document.getElementById("view-workbench");
    const today = new Date().toISOString().slice(0, 10);
    root.innerHTML = `<div class="stack">
      <div class="panel">
        <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Run research</h2>
        <p class="hint" style="margin:0 0 .85rem;">Starts the multi-agent desk for one symbol, using your current book when available. Runs can take several minutes.</p>
        <div class="grid-2">
          <div class="form-row field"><label for="run-symbol">Symbol</label><input id="run-symbol" placeholder="NVDA" /></div>
          <div class="form-row field"><label for="run-date">Trade date</label><input id="run-date" type="date" value="${today}" /></div>
        </div>
        <div class="actions">
          <button type="button" class="btn-primary" id="start-run">Run research</button>
        </div>
        <div id="run-progress" class="meta" style="margin-top:.85rem;"></div>
      </div>
      <div class="grid-2">
        <div class="panel">
          <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Analysis runs</h2>
          <div id="runs" class="list"></div>
        </div>
        <div class="panel">
          <h2 style="margin:0 0 .75rem;font-family:var(--font-display);font-size:1.25rem;">Theses</h2>
          <div id="theses" class="list"></div>
          <div class="form-row field" style="margin-top:1rem;"><label for="from-run">Create thesis from run id</label><input id="from-run" placeholder="ar_…" /></div>
          <div class="actions"><button type="button" class="btn-primary" id="create-thesis">Create from run</button></div>
        </div>
      </div>
    </div>`;

    async function loadLists() {
      const runs = await api("/v1/runs?limit=40");
      const runsEl = root.querySelector("#runs");
      runsEl.innerHTML = runs.length
        ? runs
            .map(
              (r) => `<article class="row">
                <strong>${escapeHtml(r.symbol)}</strong>
                <div class="meta">${escapeHtml(r.trade_date)} · ${escapeHtml(r.status)} · ${escapeHtml(r.final_rating || "no rating")}</div>
                <div class="mono">${escapeHtml(r.id)}</div>
                <div class="actions">
                  <button type="button" class="btn" data-thesis="${escapeHtml(r.id)}" ${r.status === "completed" ? "" : "disabled"}>Create thesis</button>
                </div>
              </article>`
            )
            .join("")
        : empty("No durable runs yet. Use Run research above.");

      runsEl.querySelectorAll("[data-thesis]").forEach((btn) => {
        btn.onclick = async () => {
          root.querySelector("#from-run").value = btn.dataset.thesis;
          root.querySelector("#create-thesis").click();
        };
      });

      const theses = await api("/v1/theses");
      const thesesEl = root.querySelector("#theses");
      thesesEl.innerHTML = theses.length
        ? theses
            .map(
              (t) => `<article class="row">
                <strong>${escapeHtml(t.symbol || t.id)}</strong>
                <div class="meta">${escapeHtml(t.status || "active")} · snapshot ${escapeHtml(t.current_snapshot_id || "—")}</div>
              </article>`
            )
            .join("")
        : empty("No theses yet.");
    }

    async function pollRun(runId) {
      const progress = root.querySelector("#run-progress");
      let lastSeq = -1;
      const terminal = new Set(["completed", "failed", "cancelled", "partially_completed"]);
      for (let i = 0; i < 180; i += 1) {
        const run = await api(`/v1/runs/${runId}`);
        const events = await api(`/v1/runs/${runId}/events?after_sequence=${lastSeq}`);
        if (events.length) {
          lastSeq = events[events.length - 1].sequence;
          const lines = events.map((e) => `${e.event_type}: ${e.message || ""}`).join(" · ");
          progress.innerHTML = `<div><strong>${escapeHtml(run.status)}</strong> · ${escapeHtml(run.final_rating || "…")}</div><div class="mono">${escapeHtml(lines)}</div>`;
        } else {
          progress.innerHTML = `<div><strong>${escapeHtml(run.status)}</strong></div>`;
        }
        if (terminal.has(run.status)) {
          if (run.status === "completed") {
            setStatus(`Research complete: ${run.symbol} → ${run.final_rating || "done"}`, "ok");
            root.querySelector("#from-run").value = run.id;
          } else {
            setStatus(run.error || `Run ${run.status}`, "error");
          }
          await loadLists();
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      setStatus("Still running — refresh Workbench later", "error");
    }

    root.querySelector("#start-run").onclick = async () => {
      const symbol = root.querySelector("#run-symbol").value.trim().toUpperCase();
      const tradeDate = root.querySelector("#run-date").value;
      const progress = root.querySelector("#run-progress");
      if (!symbol) {
        setStatus("Enter a symbol first", "error");
        return;
      }
      try {
        root.querySelector("#start-run").disabled = true;
        progress.textContent = "Queueing…";
        setStatus(`Starting research for ${symbol}…`);
        const created = await api("/v1/runs/start", {
          method: "POST",
          json: { symbol, trade_date: tradeDate || undefined },
        });
        progress.innerHTML = `<div class="mono">Queued ${escapeHtml(created.id)}</div>`;
        await pollRun(created.id);
      } catch (err) {
        setStatus(err.message, "error");
        progress.textContent = err.message;
      } finally {
        root.querySelector("#start-run").disabled = false;
      }
    };

    root.querySelector("#create-thesis").onclick = async () => {
      const runId = root.querySelector("#from-run").value.trim();
      if (!runId) return;
      try {
        const created = await api("/v1/theses/from-run", {
          method: "POST",
          json: { run_id: runId, stance: "initiate" },
        });
        setStatus(`Thesis proposal ${created.id || "created"}`, "ok");
        await loadLists();
      } catch (err) {
        setStatus(err.message, "error");
      }
    };

    await loadLists();
  }

  async function renderJournal() {
    const root = document.getElementById("view-journal");
    const entries = await api("/v1/journal?limit=50");
    root.innerHTML = `<div class="panel list">${
      entries.length
        ? entries
            .map(
              (e) => `<article class="row">
                <strong>${escapeHtml(e.symbol || e.id)}</strong>
                <div class="meta">${escapeHtml(e.decision || e.stance || "entry")} · ${escapeHtml(e.created_at || "")}</div>
                <div>${escapeHtml(e.rationale || e.summary || "")}</div>
              </article>`
            )
            .join("")
        : empty("Journal is empty. Log decisions after accepting a thesis.")
    }</div>`;
  }

  async function renderSettings() {
    const root = document.getElementById("view-settings");
    let me = null;
    let health = null;
    try {
      me = await api("/v1/workspaces/me");
      health = await fetch("/health").then((r) => r.json());
    } catch (err) {
      setStatus(err.message, "error");
    }
    root.innerHTML = `<div class="panel stack">
      <div>
        <div class="meta">API health</div>
        <div class="mono">${escapeHtml(JSON.stringify(health || { status: "unreachable" }))}</div>
      </div>
      <div>
        <div class="meta">Active workspace</div>
        <div class="mono">${escapeHtml(JSON.stringify(me || { id: workspaceId() }))}</div>
      </div>
      <p class="hint">Core journeys use the durable /v1 API. Auth (Phase 4) will replace the workspace header.</p>
    </div>`;
  }

  const RENDERERS = {
    intelligence: renderIntelligence,
    portfolio: renderPortfolio,
    research: renderResearch,
    workbench: renderWorkbench,
    journal: renderJournal,
    settings: renderSettings,
  };

  async function show(name) {
    view = name;
    const [title, sub] = META[name];
    els.title.textContent = title;
    els.sub.textContent = sub;
    els.nav.querySelectorAll("button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === name);
    });
    document.querySelectorAll(".view").forEach((section) => {
      const active = section.id === `view-${name}`;
      section.hidden = !active;
      section.classList.toggle("active", active);
    });
    try {
      setStatus("Loading…");
      await RENDERERS[name]();
      setStatus("Ready", "ok");
    } catch (err) {
      document.getElementById(`view-${name}`).innerHTML = `<div class="panel">${empty(err.message)}</div>`;
      setStatus(err.message, "error");
    }
  }

  function fmtMoney(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value));
  }

  function fmtPct(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    const n = Number(value);
    return `${n <= 1 ? (n * 100).toFixed(0) : n.toFixed(0)}%`;
  }

  els.workspace.value = localStorage.getItem(STORAGE_KEY) || "ws_local";
  els.workspace.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEY, workspaceId());
    show(view);
  });
  els.refresh.addEventListener("click", () => show(view));
  els.nav.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-view]");
    if (btn) show(btn.dataset.view);
  });

  show("intelligence");
})();
