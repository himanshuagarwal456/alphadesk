"""Render a :class:`Feed` to a self-contained HTML page.

Vertical scroll = distinguishable story posts (social-feed style).
Horizontal scroll = the album that tells one complete story, starting with
high-level commentary and listing every affected symbol.
"""

from __future__ import annotations

import json
from pathlib import Path

from .feed_schema import Feed

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  :root {
    --ink:#1a221c; --muted:#5c6a60; --line:rgba(26,34,28,.12);
    --paper:#ebe4d6; --post:#fffdf8; --accent:#0f6b5c; --warn:#8a4b1f;
    --shadow:0 14px 34px rgba(26,34,28,.10);
    --display:"Fraunces",Georgia,serif; --body:"IBM Plex Sans","Segoe UI",sans-serif;
  }
  * { box-sizing:border-box; }
  html, body {
    margin:0; height:100%; color:var(--ink); font-family:var(--body);
    background:
      radial-gradient(900px 420px at 8% -10%, rgba(15,107,92,.14), transparent 55%),
      linear-gradient(165deg, #e7efe8 0%, var(--paper) 48%, #e8e0d0 100%);
  }
  #feed {
    height:100vh; overflow-y:scroll; scroll-snap-type:y mandatory;
    padding:18px 14px 48px; max-width:720px; margin:0 auto;
  }
  .story {
    scroll-snap-align:start; min-height:calc(100vh - 36px);
    background:var(--post); border:1px solid var(--line); border-radius:18px;
    box-shadow:var(--shadow); margin:0 0 22px; display:flex; flex-direction:column;
    overflow:hidden; animation:rise .28s ease;
  }
  .story:nth-child(even) { border-top:4px solid var(--accent); }
  .story:nth-child(odd) { border-top:4px solid var(--warn); }
  @keyframes rise { from { opacity:0; transform:translateY(8px);} to { opacity:1; transform:none;} }
  .story-head { padding:16px 18px 10px; border-bottom:1px solid var(--line); }
  .story-kicker {
    text-transform:uppercase; letter-spacing:.08em; font-size:11px; color:var(--muted);
    font-weight:600; margin-bottom:4px;
  }
  .story-title { font-family:var(--display); font-size:1.55rem; line-height:1.15; letter-spacing:-.02em; }
  .story-sum { color:var(--muted); font-size:.92rem; margin-top:6px; line-height:1.4; }
  .symbol-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  .sym {
    font-size:12px; font-weight:600; padding:4px 9px; border-radius:999px;
    background:rgba(15,107,92,.10); color:var(--accent); border:1px solid rgba(15,107,92,.18);
  }
  .album { flex:1; display:flex; overflow-x:scroll; scroll-snap-type:x mandatory; }
  .card {
    min-width:100%; width:100%; scroll-snap-align:start; padding:14px 18px 18px;
    display:flex; flex-direction:column; gap:8px;
  }
  .card-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .kind {
    text-transform:uppercase; font-size:10px; letter-spacing:.08em; font-weight:700;
    color:#f7fff9; background:var(--accent); padding:3px 9px; border-radius:8px;
  }
  .kind.hook { background:#1f4e45; }
  .kind.context { background:#5c6a60; }
  .kind.tension { background:var(--warn); }
  .kind.verdict { background:#0f6b5c; }
  .kind.evidence { background:#2f5d50; }
  .badges { display:flex; gap:6px; flex-wrap:wrap; }
  .badge {
    font-size:11px; border:1px solid var(--line); background:#f3efe6;
    padding:2px 8px; border-radius:8px; color:var(--ink);
  }
  .headline {
    font-family:var(--display); font-size:1.35rem; font-weight:650;
    line-height:1.25; letter-spacing:-.02em; margin:2px 0 4px;
  }
  .chart {
    flex:1; min-height:240px; background:#f3efe6; border:1px solid var(--line);
    border-radius:12px; overflow:hidden;
  }
  .comments {
    margin-top:6px; border-top:1px solid var(--line); padding-top:10px;
    display:flex; flex-direction:column; gap:10px;
  }
  .comments-label {
    font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
    color:var(--muted);
  }
  .comment {
    display:grid; grid-template-columns:36px 1fr; gap:10px; align-items:start;
  }
  .avatar {
    width:36px; height:36px; border-radius:50%; display:grid; place-items:center;
    background:rgba(15,107,92,.14); color:var(--accent); font-size:12px; font-weight:700;
  }
  .comment-bubble {
    background:#f3efe6; border:1px solid var(--line); border-radius:14px 14px 14px 4px;
    padding:8px 11px;
  }
  .comment-meta { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-bottom:3px; }
  .comment-agent { font-size:13px; font-weight:700; color:var(--ink); }
  .comment-role {
    font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.04em;
    color:var(--accent); background:rgba(15,107,92,.10); padding:2px 6px; border-radius:6px;
  }
  .comment-text { color:var(--ink); font-size:13px; line-height:1.45; }
  .impact { color:var(--muted); font-size:12px; line-height:1.4; }
  details.sources { margin-top:4px; }
  details summary { color:var(--accent); cursor:pointer; font-size:13px; font-weight:500; }
  .source { border-top:1px solid var(--line); padding:8px 0; }
  .source a { color:var(--ink); font-size:13px; font-weight:600; text-decoration:none; }
  .source-meta, .source-summary { color:var(--muted); font-size:12px; margin-top:2px; line-height:1.4; }
  .dots { display:flex; gap:6px; justify-content:center; padding:8px 0 14px; }
  .dot { width:7px; height:7px; border-radius:50%; background:rgba(26,34,28,.18); }
  .dot.active { background:var(--accent); }
  .empty { padding:48px 20px; text-align:center; color:var(--muted); }
  .hint-swipe {
    color:var(--muted); font-size:11px; text-align:right; padding:0 18px 8px;
  }
  .learn-btn {
    appearance:none; border:1px solid rgba(15,107,92,.35); background:rgba(15,107,92,.08);
    color:var(--accent); font:inherit; font-weight:600; font-size:13px;
    padding:8px 12px; border-radius:10px; cursor:pointer; margin-top:6px; align-self:flex-start;
  }
  .learn-btn:hover { background:rgba(15,107,92,.14); }
  .drawer-backdrop {
    position:fixed; inset:0; background:rgba(26,34,28,.35); z-index:40; display:none;
  }
  .drawer-backdrop.is-open { display:block; }
  .drawer {
    position:fixed; top:0; right:0; width:min(420px,100vw); height:100vh; z-index:50;
    background:rgba(255,252,246,.98); border-left:1px solid var(--line);
    box-shadow:-16px 0 36px rgba(26,34,28,.12); display:none; flex-direction:column;
    animation:slide-in .2s ease;
  }
  .drawer.is-open { display:flex; }
  .drawer[hidden], .drawer-backdrop[hidden] { display:none !important; }
  @keyframes slide-in { from { transform:translateX(16px); opacity:.7;} to { transform:none; opacity:1;} }
  .drawer-head {
    display:flex; justify-content:space-between; gap:12px; align-items:flex-start;
    padding:16px 16px 12px; border-bottom:1px solid var(--line);
  }
  .drawer-kicker {
    margin:0 0 4px; color:var(--accent); font-size:11px; font-weight:700;
    letter-spacing:.06em; text-transform:uppercase;
  }
  .drawer-head h2 {
    margin:0; font-family:var(--display); font-size:1.35rem; line-height:1.15;
  }
  .drawer-close {
    appearance:none; border:1px solid var(--line); background:#fffdf8;
    font:inherit; padding:6px 10px; border-radius:8px; cursor:pointer; flex-shrink:0;
  }
  .drawer-body { overflow:auto; padding:14px 16px 28px; display:grid; gap:14px; }
  .learn-block h3 { margin:0 0 4px; font-family:var(--display); font-size:1.02rem; }
  .learn-block p { margin:0; line-height:1.5; color:var(--ink); font-size:.95rem; }
  .concept-pick {
    width:100%; text-align:left; appearance:none; border:1px solid var(--line);
    background:#fffdf8; border-radius:12px; padding:10px 12px; cursor:pointer; font:inherit;
  }
  .concept-pick strong { display:block; margin-bottom:2px; }
  .resource-list { margin:0; padding-left:18px; display:grid; gap:6px; }
  .resource-list a { color:var(--accent); font-weight:600; text-decoration:none; }
  .resource-list a:hover { text-decoration:underline; }
  body.drawer-open { overflow:hidden; }
</style>
</head>
<body>
<div id="feed"></div>
<div id="learn-host"></div>
<script>
const FEED = __FEED_JSON__;

function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt != null) e.textContent = txt;
  return e;
}

function ensureLearnHost() {
  const host = document.getElementById("learn-host");
  if (host.dataset.ready) return host;
  host.innerHTML = `
    <div class="drawer-backdrop" id="learn-backdrop" hidden></div>
    <aside class="drawer" id="learn-drawer" hidden aria-hidden="true">
      <div class="drawer-head">
        <div>
          <p class="drawer-kicker">Learn More</p>
          <h2 id="learn-title">Concept</h2>
        </div>
        <button type="button" class="drawer-close" id="learn-close">Close</button>
      </div>
      <div class="drawer-body" id="learn-body"></div>
    </aside>`;
  host.dataset.ready = "1";
  host.querySelector("#learn-close").onclick = closeLearnMore;
  host.querySelector("#learn-backdrop").onclick = closeLearnMore;
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closeLearnMore();
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

function openLearnMore(briefOrItems, cardTitle) {
  ensureLearnHost();
  const drawer = document.getElementById("learn-drawer");
  const backdrop = document.getElementById("learn-backdrop");
  backdrop.hidden = false;
  drawer.hidden = false;
  backdrop.classList.add("is-open");
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");

  // New shape: card briefing object with nested concepts.
  if (briefOrItems && !Array.isArray(briefOrItems) && briefOrItems.what_this_means) {
    renderLearnBrief(briefOrItems);
    return;
  }
  const items = Array.isArray(briefOrItems) ? briefOrItems : [];
  if (!items.length) return;
  // Legacy: list of concepts only — still open on the card title, then terms.
  renderLearnBrief({
    title: cardTitle || "Learn More",
    headline: "",
    what_this_means: "Open a key term below to unpack language used on this card.",
    why_it_matters: "These concepts help you interpret the claim — they are not the card itself.",
    what_to_check: "Pick the term that blocked understanding, then return to the card decision.",
    agent_takeaways: [],
    concepts: items,
  });
}

function renderLearnBrief(brief) {
  const body = document.getElementById("learn-body");
  document.getElementById("learn-title").textContent = brief.title || "Learn More";
  body.innerHTML = "";

  if (brief.headline) {
    body.appendChild(el("p", "story-sum", brief.headline));
  }

  const meaning = el("section", "learn-block");
  meaning.appendChild(el("h3", null, "What this card means"));
  meaning.appendChild(el("p", null, brief.what_this_means || ""));
  body.appendChild(meaning);

  const why = el("section", "learn-block");
  why.appendChild(el("h3", null, "Why it matters here"));
  why.appendChild(el("p", null, brief.why_it_matters || ""));
  body.appendChild(why);

  if (brief.what_to_check) {
    const check = el("section", "learn-block");
    check.appendChild(el("h3", null, "What to check next"));
    check.appendChild(el("p", null, brief.what_to_check));
    body.appendChild(check);
  }

  if (brief.agent_takeaways && brief.agent_takeaways.length) {
    const takes = el("section", "learn-block");
    takes.appendChild(el("h3", null, "Agent takeaways"));
    const ul = el("ul", "resource-list");
    brief.agent_takeaways.forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      ul.appendChild(li);
    });
    takes.appendChild(ul);
    body.appendChild(takes);
  }

  const concepts = brief.concepts || [];
  if (concepts.length) {
    const terms = el("section", "learn-block");
    terms.appendChild(el("h3", null, "Key terms on this card"));
    terms.appendChild(el("p", "source-meta", "Optional glossary — tap a term for a deeper definition."));
    concepts.forEach((item) => {
      const btn = el("button", "concept-pick");
      btn.type = "button";
      btn.appendChild(el("strong", null, item.title));
      btn.appendChild(el("div", "source-meta", (item.difficulty || "") + " · ~" + (item.estimated_read_time || 3) + " min"));
      btn.appendChild(el("div", "source-summary", item.short_definition || ""));
      btn.onclick = () => renderLearnItem(item, brief);
      terms.appendChild(btn);
    });
    body.appendChild(terms);
  }
}

function renderLearnItem(item, brief) {
  const body = document.getElementById("learn-body");
  document.getElementById("learn-title").textContent = item.title;
  body.innerHTML = "";
  body.appendChild(el("p", "story-sum", item.short_definition || ""));

  const why = el("section", "learn-block");
  why.appendChild(el("h3", null, "Why it matters on this card"));
  why.appendChild(el("p", null, item.why_it_matters || ""));
  body.appendChild(why);

  const expl = el("section", "learn-block");
  expl.appendChild(el("h3", null, "Explanation"));
  expl.appendChild(el("p", null, item.explanation || item.short_definition || ""));
  body.appendChild(expl);

  if (item.resources && item.resources.length) {
    const res = el("section", "learn-block");
    res.appendChild(el("h3", null, "Further reading"));
    const ul = el("ul", "resource-list");
    item.resources.forEach((r) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = r.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = r.title;
      li.appendChild(a);
      li.appendChild(el("span", "source-meta", " · " + (r.provider || "")));
      ul.appendChild(li);
    });
    res.appendChild(ul);
    body.appendChild(res);
  }

  if (brief) {
    const back = el("button", "learn-btn", "← Back to this card");
    back.type = "button";
    back.onclick = () => renderLearnBrief(brief);
    body.appendChild(back);
  }
}

function initials(name) {
  return String(name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "?";
}

function renderComments(comments) {
  const wrap = el("div", "comments");
  wrap.appendChild(el("div", "comments-label", "Comments"));
  (comments || []).forEach((comment) => {
    const row = el("div", "comment");
    row.appendChild(el("div", "avatar", initials(comment.agent)));
    const bubble = el("div", "comment-bubble");
    const meta = el("div", "comment-meta");
    meta.appendChild(el("span", "comment-agent", comment.agent || "Agent"));
    if (comment.role) meta.appendChild(el("span", "comment-role", comment.role));
    bubble.appendChild(meta);
    bubble.appendChild(el("div", "comment-text", comment.text || ""));
    row.appendChild(bubble);
    wrap.appendChild(row);
  });
  return wrap;
}

function renderCard(card) {
  const c = el("article", "card");
  const head = el("div", "card-head");
  head.appendChild(el("span", "kind " + card.kind, card.title || card.kind));
  const badges = el("div", "badges");
  (card.badges || []).forEach(b => badges.appendChild(el("span", "badge", b)));
  (card.symbols || []).forEach(s => badges.appendChild(el("span", "sym", s)));
  head.appendChild(badges);
  c.appendChild(head);
  c.appendChild(el("h2", "headline", card.headline || ""));
  if (card.chart) {
    const chart = el("div", "chart");
    c.appendChild(chart);
    const fig = card.chart;
    requestAnimationFrame(() => Plotly.newPlot(chart, fig.data || [], fig.layout || {},
      {responsive:true, displayModeBar:false}));
  }
  if (card.comments && card.comments.length) {
    c.appendChild(renderComments(card.comments));
  }
  if (card.portfolio_impact) {
    c.appendChild(el("div", "impact", "Portfolio impact: " + card.portfolio_impact));
  }
  if (card.evidence && card.evidence.length) {
    c.appendChild(renderSources(card.evidence));
  }
  if (card.learn_brief || (card.learn_more && card.learn_more.length)) {
    const btn = el("button", "learn-btn", "Learn More");
    btn.type = "button";
    btn.onclick = () => openLearnMore(
      card.learn_brief || card.learn_more,
      card.title || "Learn More"
    );
    c.appendChild(btn);
  }
  return c;
}

function renderSources(evidence) {
  const wrap = el("details", "sources");
  wrap.appendChild(el("summary", null, "Sources (" + evidence.length + ")"));
  evidence.forEach(source => {
    const item = el("div", "source");
    const link = document.createElement("a");
    link.textContent = source.title || "Source";
    if (source.source_url) {
      link.href = source.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    item.appendChild(link);
    const meta = [source.publisher, source.published_at, source.provider_id]
      .filter(Boolean).join(" · ");
    if (meta) item.appendChild(el("div", "source-meta", meta));
    if (source.summary) item.appendChild(el("div", "source-summary", source.summary));
    wrap.appendChild(item);
  });
  return wrap;
}

function renderStory(nrv) {
  const section = el("section", "story");
  const head = el("div", "story-head");
  const kicker = (nrv.meta && nrv.meta.story_kind) ? String(nrv.meta.story_kind).replaceAll("_", " ") : "story";
  head.appendChild(el("div", "story-kicker", kicker));
  head.appendChild(el("div", "story-title", nrv.title || nrv.symbol || "Story"));
  if (nrv.summary) head.appendChild(el("div", "story-sum", nrv.summary));
  const syms = el("div", "symbol-row");
  const list = (nrv.symbols && nrv.symbols.length) ? nrv.symbols : (nrv.symbol ? [nrv.symbol] : []);
  list.forEach(s => syms.appendChild(el("span", "sym", s)));
  head.appendChild(syms);
  section.appendChild(head);

  if ((nrv.cards || []).length > 1) {
    section.appendChild(el("div", "hint-swipe", "Swipe sideways for the full story →"));
  }

  const album = el("div", "album");
  (nrv.cards || []).forEach(card => album.appendChild(renderCard(card)));
  section.appendChild(album);

  const dots = el("div", "dots");
  (nrv.cards || []).forEach((_, i) => dots.appendChild(el("span", "dot" + (i === 0 ? " active" : ""))));
  section.appendChild(dots);
  album.addEventListener("scroll", () => {
    const i = Math.round(album.scrollLeft / Math.max(album.clientWidth, 1));
    dots.querySelectorAll(".dot").forEach((d, j) => d.classList.toggle("active", i === j));
  });
  return section;
}

const feedEl = document.getElementById("feed");
if (!FEED.narratives || FEED.narratives.length === 0) {
  feedEl.appendChild(el("div", "empty", "No stories yet — run research to populate the feed."));
} else {
  FEED.narratives.forEach(nrv => feedEl.appendChild(renderStory(nrv)));
}
</script>
</body>
</html>
"""


def render_feed_html(feed: Feed, *, title: str = "AlphaDesk — Feed") -> str:
    """Return the full HTML document for ``feed`` as a string."""
    feed_json = json.dumps(feed.model_dump(mode="json"))
    return _TEMPLATE.replace("__TITLE__", title).replace("__FEED_JSON__", feed_json)


def write_feed_html(feed: Feed, path: str | Path, *, title: str = "AlphaDesk — Feed") -> Path:
    """Write the rendered feed to ``path`` and return it."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_feed_html(feed, title=title), encoding="utf-8")
    return path
