(() => {
  const STORAGE_KEY = "alphadesk.workspaceId";
  const META = {
    workbench: ["Run research", "Start a multi-agent analysis and turn it into a thesis."],
    portfolio: ["Portfolio", "Current book, coverage, and import workflow."],
    research: ["Documents", "Private uploads that stay inside this workspace."],
    intelligence: ["Intelligence", "Material changes and saved intelligence cards."],
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
      root.innerHTML = `<div class="panel stack">
        <h2 style="margin:0;font-family:var(--font-display);font-size:1.35rem;">Learn More</h2>
        ${empty("No intelligence cards yet. Create a demo card, then open Learn More on it.")}
        <div class="actions">
          <button type="button" class="btn-primary" id="demo-card">Create demo card</button>
          <button type="button" class="btn" id="browse-concepts">Browse concepts</button>
          <button type="button" class="btn" id="empty-monitor-tick">Run monitor tick</button>
        </div>
      </div>`;
      root.querySelector("#demo-card")?.addEventListener("click", async () => {
        try {
          setStatus("Creating demo card…");
          await api("/v1/knowledge/demo-card", { method: "POST", json: {} });
          setStatus("Demo card ready", "ok");
          await renderIntelligence();
        } catch (err) {
          setStatus(err.message, "error");
        }
      });
      root.querySelector("#browse-concepts")?.addEventListener("click", () => openConceptBrowser());
      root.querySelector("#empty-monitor-tick")?.addEventListener("click", async () => {
        try {
          setStatus("Running monitor…");
          await api("/v1/monitoring/tick", { method: "POST", json: {} });
          setStatus("Monitor tick complete", "ok");
          await renderIntelligence();
        } catch (err) {
          setStatus(err.message, "error");
        }
      });
      return;
    }
    root.innerHTML = `<div class="panel list">${cards
      .map(
        (c) => `<article class="row" data-card-id="${escapeHtml(c.id)}">
          <strong>${escapeHtml(c.title || c.id)}</strong>
          <div class="meta">${escapeHtml(c.symbol || "—")} · ${escapeHtml(c.card_type || "card")} · ${escapeHtml(c.status || "new")}</div>
          <div>${escapeHtml(c.headline || c.body || "")}</div>
          <div class="actions">
            <button type="button" class="btn learn-more" data-card-id="${escapeHtml(c.id)}">Learn More</button>
            <button type="button" class="btn card-status" data-card-id="${escapeHtml(c.id)}" data-status="reviewed">Mark reviewed</button>
            <button type="button" class="btn card-status" data-card-id="${escapeHtml(c.id)}" data-status="saved">Save</button>
            <button type="button" class="btn card-status" data-card-id="${escapeHtml(c.id)}" data-status="dismissed">Dismiss</button>
          </div>
        </article>`
      )
      .join("")}</div>
      <div class="panel" style="margin-top:1rem;">
        <div class="actions">
          <button type="button" class="btn" id="run-monitor-tick">Run monitor tick</button>
          <button type="button" class="btn" id="browse-concepts-intel">Browse concepts</button>
        </div>
        <div id="monitor-health" class="meta" style="margin-top:.75rem;"></div>
      </div>`;
    root.querySelectorAll("button.learn-more").forEach((btn) => {
      btn.addEventListener("click", () => openLearnMore(btn.dataset.cardId));
    });
    root.querySelectorAll("button.card-status").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api(`/v1/cards/${encodeURIComponent(btn.dataset.cardId)}/status`, {
            method: "POST",
            json: { status: btn.dataset.status },
          });
          await renderIntelligence();
        } catch (err) {
          setStatus(err.message, "error");
        }
      });
    });
    root.querySelector("#browse-concepts-intel")?.addEventListener("click", () => openConceptBrowser());
    root.querySelector("#run-monitor-tick")?.addEventListener("click", async () => {
      try {
        setStatus("Running monitor…");
        const run = await api("/v1/monitoring/tick", { method: "POST", json: {} });
        const health = await api("/v1/monitoring/health");
        root.querySelector("#monitor-health").textContent =
          `Tick ${run.status}: ${run.cards_created} cards · unread ${health.unread_notifications}`;
        setStatus("Monitor tick complete", "ok");
        await renderIntelligence();
      } catch (err) {
        setStatus(err.message, "error");
      }
    });
  }

  function ensureDrawer() {
    let host = document.getElementById("learn-drawer-host");
    if (host) return host;
    host = document.createElement("div");
    host.id = "learn-drawer-host";
    host.innerHTML = `
      <div class="drawer-backdrop" id="learn-backdrop" hidden></div>
      <aside class="drawer" id="learn-drawer" hidden aria-hidden="true">
        <div class="drawer-head">
          <div>
            <p class="drawer-kicker">Learn More</p>
            <h2 id="learn-title">Concept</h2>
          </div>
          <button type="button" class="btn" id="learn-close" aria-label="Close">Close</button>
        </div>
        <div class="drawer-body" id="learn-body"></div>
      </aside>`;
    document.body.appendChild(host);
    host.querySelector("#learn-close").addEventListener("click", closeLearnMore);
    host.querySelector("#learn-backdrop").addEventListener("click", closeLearnMore);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeLearnMore();
    });
    return host;
  }

  function closeLearnMore() {
    const backdrop = document.getElementById("learn-backdrop");
    const drawer = document.getElementById("learn-drawer");
    if (!backdrop || !drawer) return;
    backdrop.hidden = true;
    drawer.hidden = true;
    backdrop.classList.remove("is-open");
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("drawer-open");
  }

  function openDrawerShell() {
    ensureDrawer();
    const drawer = document.getElementById("learn-drawer");
    const backdrop = document.getElementById("learn-backdrop");
    backdrop.hidden = false;
    drawer.hidden = false;
    backdrop.classList.add("is-open");
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    document.body.classList.add("drawer-open");
    return { drawer, backdrop, body: document.getElementById("learn-body") };
  }

  async function openConceptBrowser() {
    const { body } = openDrawerShell();
    document.getElementById("learn-title").textContent = "Concept catalog";
    body.innerHTML = `<p class="meta">Loading…</p>`;
    try {
      const concepts = await api("/v1/knowledge/concepts");
      body.innerHTML = `<div class="list">${concepts
        .map(
          (c) => `<button type="button" class="row concept-pick" data-concept-id="${escapeHtml(c.id)}">
            <strong>${escapeHtml(c.title)}</strong>
            <div class="meta">${escapeHtml(c.difficulty)} · ~${escapeHtml(c.estimated_read_time)} min</div>
            <div>${escapeHtml(c.short_definition)}</div>
          </button>`
        )
        .join("")}</div>`;
      body.querySelectorAll(".concept-pick").forEach((btn) => {
        btn.addEventListener("click", () => openLearnMoreContext(btn.dataset.conceptId));
      });
    } catch (err) {
      body.innerHTML = empty(err.message);
    }
  }

  async function openLearnMore(cardId) {
    const { body } = openDrawerShell();
    document.getElementById("learn-title").textContent = "Learn More";
    body.innerHTML = `<p class="meta">Unpacking this card…</p>`;
    try {
      const brief = await api(`/v1/knowledge/cards/${encodeURIComponent(cardId)}/learn-more`);
      renderCardLearnBrief(brief, cardId);
    } catch (err) {
      body.innerHTML = empty(err.message);
    }
  }

  function renderCardLearnBrief(brief, cardId) {
    const body = document.getElementById("learn-body");
    document.getElementById("learn-title").textContent = brief.title || "Learn More";
    const concepts = brief.concepts || [];
    const resources = (brief.external_resources || [])
      .map(
        (r) => `<li>
          <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.title)}</a>
          <span class="meta"> · ${escapeHtml(r.provider)}</span>
        </li>`
      )
      .join("");
    const conceptRows = concepts
      .map(
        (c) => `<button type="button" class="row concept-pick" data-concept-id="${escapeHtml(c.id)}">
          <strong>${escapeHtml(c.title)}</strong>
          <div class="meta">${escapeHtml(c.difficulty)} · ~${escapeHtml(c.estimated_read_time)} min</div>
          <div>${escapeHtml(c.short_definition)}</div>
        </button>`
      )
      .join("");
    body.innerHTML = `
      ${brief.headline ? `<p class="lede learn-tldr">${escapeHtml(brief.headline)}</p>` : ""}
      <section class="learn-block">
        <h3>What this card means</h3>
        <p>${escapeHtml(brief.what_this_means || "")}</p>
      </section>
      <section class="learn-block">
        <h3>Why it matters here</h3>
        <p>${escapeHtml(brief.why_it_matters || "")}</p>
      </section>
      ${brief.what_to_check ? `<section class="learn-block"><h3>What to check next</h3><p>${escapeHtml(brief.what_to_check)}</p></section>` : ""}
      ${conceptRows ? `<section class="learn-block"><h3>Key terms on this card</h3><p class="meta">Optional glossary — tap a term for a deeper definition.</p><div class="list">${conceptRows}</div></section>` : ""}
      ${resources ? `<section class="learn-block"><h3>Further reading</h3><ul class="resource-list">${resources}</ul></section>` : ""}
    `;
    body.querySelectorAll(".concept-pick").forEach((btn) => {
      btn.addEventListener("click", () =>
        openLearnMoreContext(btn.dataset.conceptId, cardId)
      );
    });
  }

  async function openLearnMoreContext(conceptId, cardId = null) {
    const { body } = openDrawerShell();
    document.getElementById("learn-title").textContent = "Loading…";
    body.innerHTML = `<p class="meta">Building context…</p>`;
    try {
      const params = new URLSearchParams({ concept_id: conceptId });
      if (cardId) params.set("intelligence_card_id", cardId);
      const ctx = await api(`/v1/knowledge/context?${params.toString()}`);
      document.getElementById("learn-title").textContent = ctx.concept.title;
      const progress = ctx.user_progress || {};
      const resources = (ctx.external_resources || [])
        .map(
          (r) => `<li>
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.title)}</a>
            <span class="meta"> · ${escapeHtml(r.provider)} · ${escapeHtml(r.access_type)}</span>
          </li>`
        )
        .join("");
      const related = (ctx.related_concepts || [])
        .map(
          (c) => `<button type="button" class="chip related-concept" data-concept-id="${escapeHtml(c.id)}">${escapeHtml(c.title)}</button>`
        )
        .join("");
      body.innerHTML = `
        <p class="lede learn-tldr">${escapeHtml(ctx.concept.short_definition)}</p>
        <section class="learn-block">
          <h3>Why it matters on this card</h3>
          <p>${escapeHtml(ctx.why_it_matters)}</p>
        </section>
        <section class="learn-block">
          <h3>Explanation <span class="meta">(${escapeHtml(ctx.explanation_level)})</span></h3>
          <p>${escapeHtml(ctx.personalized_explanation)}</p>
        </section>
        <section class="learn-block">
          <h3>Portfolio example</h3>
          <p>${escapeHtml(ctx.portfolio_example)}</p>
        </section>
        ${related ? `<section class="learn-block"><h3>Related</h3><div class="chip-row">${related}</div></section>` : ""}
        ${resources ? `<section class="learn-block"><h3>Further reading</h3><ul class="resource-list">${resources}</ul></section>` : ""}
        <div class="actions learn-actions">
          ${cardId ? `<button type="button" class="btn" id="learn-back-card">← Back to this card</button>` : ""}
          <button type="button" class="btn" id="learn-save">${progress.saved ? "Unsave" : "Save"}</button>
          <button type="button" class="btn-primary" id="learn-complete">${progress.status === "completed" ? "Completed" : "Mark complete"}</button>
        </div>
        <p class="meta" id="learn-progress">Views: ${escapeHtml(progress.view_count ?? 0)} · Status: ${escapeHtml(progress.status || "not_started")}</p>
      `;
      body.querySelectorAll(".related-concept").forEach((btn) => {
        btn.addEventListener("click", () => openLearnMoreContext(btn.dataset.conceptId, cardId));
      });
      body.querySelector("#learn-back-card")?.addEventListener("click", () => openLearnMore(cardId));
      body.querySelector("#learn-save")?.addEventListener("click", async () => {
        try {
          await api(`/v1/knowledge/concepts/${encodeURIComponent(conceptId)}/progress`, {
            method: "POST",
            json: { saved: !progress.saved },
          });
          await openLearnMoreContext(conceptId, cardId);
        } catch (err) {
          setStatus(err.message, "error");
        }
      });
      body.querySelector("#learn-complete")?.addEventListener("click", async () => {
        try {
          await api(`/v1/knowledge/concepts/${encodeURIComponent(conceptId)}/progress`, {
            method: "POST",
            json: { status: "completed" },
          });
          await openLearnMoreContext(conceptId, cardId);
        } catch (err) {
          setStatus(err.message, "error");
        }
      });
    } catch (err) {
      body.innerHTML = empty(err.message);
    }
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
          <button type="button" class="btn" id="goto-learn-more">Try Learn More</button>
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
          <div id="thesis-result" class="meta" style="margin-top:.75rem;"></div>
        </div>
      </div>
    </div>`;

    root.querySelector("#goto-learn-more")?.addEventListener("click", async () => {
      try {
        setStatus("Opening Learn More…");
        await api("/v1/knowledge/demo-card", { method: "POST", json: {} });
      } catch (_) {
        /* demo card may already exist */
      }
      await show("intelligence");
    });

    async function createThesisFromRun(runId) {
      const resultEl = root.querySelector("#thesis-result");
      if (!runId) {
        setStatus("No run selected", "error");
        return;
      }
      try {
        setStatus(`Creating thesis from ${runId}…`);
        resultEl.textContent = "Creating…";
        const created = await api("/v1/theses/from-run", {
          method: "POST",
          json: { run_id: runId, accept: true },
        });
        const rating = created.snapshot?.rating || "—";
        const symbol = created.symbol || "—";
        resultEl.innerHTML = `<strong>${escapeHtml(symbol)}</strong> thesis ${escapeHtml(created.status)} · ${escapeHtml(rating)}<div class="mono">${escapeHtml(created.id || "")}</div>`;
        setStatus(`Thesis saved for ${symbol} (${rating})`, "ok");
        await loadLists();
      } catch (err) {
        resultEl.textContent = err.message;
        setStatus(err.message, "error");
      }
    }

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
                  <button type="button" class="btn-primary" data-thesis="${escapeHtml(r.id)}" ${r.status === "completed" ? "" : "disabled"}>Create thesis</button>
                </div>
              </article>`
            )
            .join("")
        : empty("No durable runs yet. Use Run research above.");

      runsEl.querySelectorAll("[data-thesis]").forEach((btn) => {
        btn.onclick = () => createThesisFromRun(btn.dataset.thesis);
      });

      const theses = await api("/v1/theses");
      const thesesEl = root.querySelector("#theses");
      thesesEl.innerHTML = theses.length
        ? theses
            .map(
              (t) => `<article class="row">
                <strong>${escapeHtml(t.symbol || t.id)}</strong>
                <div class="meta">${escapeHtml(t.status || "active")} · ${escapeHtml(t.current?.rating || t.current?.executive_summary || t.current_snapshot_id || "—")}</div>
              </article>`
            )
            .join("")
        : empty("No theses yet. Finish a run, then Create thesis.");
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
    let ready = null;
    let usage = null;
    let controls = null;
    let monHealth = null;
    try {
      me = await api("/v1/workspaces/me");
      health = await fetch("/health").then((r) => r.json());
      ready = await fetch("/health/ready").then((r) => r.json());
      usage = await api("/v1/ops/usage");
      controls = await api("/v1/monitoring/controls");
      monHealth = await api("/v1/monitoring/health");
    } catch (err) {
      setStatus(err.message, "error");
    }
    root.innerHTML = `<div class="panel stack">
      <div>
        <div class="meta">API health</div>
        <div class="mono">${escapeHtml(JSON.stringify(health || { status: "unreachable" }))}</div>
      </div>
      <div>
        <div class="meta">Readiness</div>
        <div class="mono">${escapeHtml(JSON.stringify(ready || { status: "unreachable" }))}</div>
      </div>
      <div>
        <div class="meta">Active workspace</div>
        <div class="mono">${escapeHtml(JSON.stringify(me || { id: workspaceId() }))}</div>
      </div>
      <div>
        <div class="meta">Monitoring</div>
        <div class="actions">
          <button type="button" class="btn-primary" id="toggle-monitoring">${controls && controls.monitoring_enabled === false ? "Enable monitoring" : "Pause monitoring"}</button>
          <button type="button" class="btn" id="settings-monitor-tick">Run monitor tick</button>
        </div>
        <div class="mono" style="margin-top:.5rem;">${escapeHtml(JSON.stringify(monHealth || {}))}</div>
      </div>
      <div>
        <div class="meta">Usage &amp; estimated cost</div>
        <div class="mono">${escapeHtml(JSON.stringify(usage || {}))}</div>
      </div>
      <div>
        <div class="meta">Factor exposures (Batch 1)</div>
        <div class="actions">
          <button type="button" class="btn" id="load-factors">Load factor exposures</button>
        </div>
        <div id="factor-exposures" class="mono" style="margin-top:.5rem;"></div>
      </div>
      <p class="hint">Core journeys use the durable /v1 API. Auth (Phase 4) will replace the workspace header.</p>
    </div>`;
    root.querySelector("#toggle-monitoring")?.addEventListener("click", async () => {
      try {
        const enabled = !(controls && controls.monitoring_enabled === false);
        await api("/v1/monitoring/controls", {
          method: "PUT",
          json: { monitoring_enabled: !enabled },
        });
        await renderSettings();
      } catch (err) {
        setStatus(err.message, "error");
      }
    });
    root.querySelector("#settings-monitor-tick")?.addEventListener("click", async () => {
      try {
        await api("/v1/monitoring/tick", { method: "POST", json: {} });
        await renderSettings();
      } catch (err) {
        setStatus(err.message, "error");
      }
    });
    root.querySelector("#load-factors")?.addEventListener("click", async () => {
      const el = root.querySelector("#factor-exposures");
      try {
        setStatus("Loading factor exposures…");
        const report = await api("/v1/portfolios/current/factor-exposures");
        const top = (report.exposures || [])
          .filter((e) => e.category === "style" || e.category === "market")
          .slice(0, 12)
          .map((e) => `${e.factor_code}: ${Number(e.portfolio_exposure).toFixed(2)}`)
          .join(" · ");
        el.textContent = `coverage ${(report.coverage * 100).toFixed(0)}% · ${top || "no style exposures"}`;
        setStatus("Factor exposures ready", "ok");
      } catch (err) {
        el.textContent = err.message;
        setStatus(err.message, "error");
      }
    });
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

  show("workbench");
})();
