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
  .body { color:var(--muted); font-size:13px; line-height:1.5; white-space:pre-wrap;
    max-height:28vh; overflow:auto; }
  details.body-wrap, details.sources { margin-top:4px; }
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
</style>
</head>
<body>
<div id="feed"></div>
<script>
const FEED = __FEED_JSON__;

function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt != null) e.textContent = txt;
  return e;
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
  if (card.body) {
    const wrap = el("details", "body-wrap");
    wrap.appendChild(el("summary", null, "Details"));
    wrap.appendChild(el("div", "body", card.body));
    c.appendChild(wrap);
  }
  if (card.portfolio_impact) {
    c.appendChild(el("div", "body", "Portfolio impact: " + card.portfolio_impact));
  }
  if (card.evidence && card.evidence.length) {
    c.appendChild(renderSources(card.evidence));
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
