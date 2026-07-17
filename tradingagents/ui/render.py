"""Render a :class:`Feed` to a self-contained HTML page.

No server, no build step: one file that embeds the feed JSON, pulls Plotly.js
from a CDN, and lays the feed out with CSS scroll-snap — **vertical** snap
between narratives, **horizontal** snap between the cards of one narrative
(the photo-album). Opening the file in a browser gives the two-axis swipe feel.
The renderer only consumes the :mod:`.feed_schema` contract, so swapping in a
React front-end later is a drop-in.
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
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  :root { --bg:#0e1117; --card:#161b22; --edge:#2a2f3a; --fg:#e6edf3; --dim:#8b949e; --accent:#4c9be8; }
  * { box-sizing: border-box; }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  #feed { height:100vh; overflow-y:scroll; scroll-snap-type:y mandatory; }
  .narrative { height:100vh; scroll-snap-align:start; display:flex; flex-direction:column;
    border-bottom:1px solid var(--edge); position:relative; }
  .nrv-head { padding:10px 16px 4px; }
  .nrv-title { font-size:18px; font-weight:700; }
  .nrv-sum { color:var(--dim); font-size:13px; margin-top:2px; }
  .album { flex:1; display:flex; overflow-x:scroll; scroll-snap-type:x mandatory; gap:0; }
  .card { min-width:100%; width:100%; scroll-snap-align:start; padding:12px 16px 20px;
    display:flex; flex-direction:column; }
  .card-head { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
  .kind { text-transform:uppercase; font-size:10px; letter-spacing:.08em; color:var(--bg);
    background:var(--accent); padding:2px 8px; border-radius:10px; font-weight:700; }
  .kind.tension { background:#e0873a; } .kind.verdict { background:#2ca02c; }
  .kind.hook { background:#c678dd; }
  .badges { display:flex; gap:6px; flex-wrap:wrap; }
  .badge { font-size:11px; color:var(--fg); border:1px solid var(--edge); background:var(--card);
    padding:2px 8px; border-radius:10px; }
  .headline { font-size:20px; font-weight:650; line-height:1.25; margin:2px 0 10px; }
  .chart { flex:1; min-height:220px; background:var(--card); border:1px solid var(--edge);
    border-radius:12px; overflow:hidden; }
  .body { color:var(--dim); font-size:13px; line-height:1.5; white-space:pre-wrap;
    max-height:26vh; overflow:auto; margin-top:10px; }
  details.body-wrap { margin-top:10px; }
  details.body-wrap summary { color:var(--accent); cursor:pointer; font-size:13px; }
  .dots { display:flex; gap:5px; justify-content:center; padding:6px 0 10px; }
  .dot { width:6px; height:6px; border-radius:50%; background:var(--edge); }
  .dot.active { background:var(--accent); }
  .empty { padding:40px; text-align:center; color:var(--dim); }
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
  return c;
}

function renderNarrative(nrv) {
  const section = el("section", "narrative");
  const head = el("div", "nrv-head");
  head.appendChild(el("div", "nrv-title", nrv.title || nrv.symbol));
  if (nrv.summary) head.appendChild(el("div", "nrv-sum", nrv.summary));
  section.appendChild(head);

  const album = el("div", "album");
  (nrv.cards || []).forEach(card => album.appendChild(renderCard(card)));
  section.appendChild(album);

  const dots = el("div", "dots");
  (nrv.cards || []).forEach((_, i) => dots.appendChild(el("span", "dot" + (i === 0 ? " active" : ""))));
  section.appendChild(dots);
  album.addEventListener("scroll", () => {
    const i = Math.round(album.scrollLeft / album.clientWidth);
    dots.querySelectorAll(".dot").forEach((d, j) => d.classList.toggle("active", i === j));
  });
  return section;
}

const feedEl = document.getElementById("feed");
if (!FEED.narratives || FEED.narratives.length === 0) {
  feedEl.appendChild(el("div", "empty", "No narratives yet — run an analysis to populate the feed."));
} else {
  FEED.narratives.forEach(nrv => feedEl.appendChild(renderNarrative(nrv)));
}
</script>
</body>
</html>
"""


def render_feed_html(feed: Feed, *, title: str = "AlphaDesk — FinTok") -> str:
    """Return the full HTML document for ``feed`` as a string."""
    feed_json = json.dumps(feed.model_dump(mode="json"))
    return _TEMPLATE.replace("__TITLE__", title).replace("__FEED_JSON__", feed_json)


def write_feed_html(feed: Feed, path: str | Path, *, title: str = "AlphaDesk — FinTok") -> Path:
    """Write the rendered feed to ``path`` and return it."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_feed_html(feed, title=title), encoding="utf-8")
    return path
