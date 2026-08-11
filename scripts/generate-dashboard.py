"""Render docs/index.html from docs/dashboard-data.json.

Standalone static page (inline CSS, no external fonts or scripts) so it hosts
cleanly on GitHub Pages. Shows, per package and per iflow, whether git is still
in sync with CPI.
"""

import os
import re
import sys
import json
import html
import datetime

DATA_FILE = os.path.join("docs", "dashboard-data.json")
OUT_FILE = os.path.join("docs", "index.html")

STATUS_LABEL = {
    "up-to-date": "In sync",
    "outdated": "Drift",
    "missing-in-git": "Not in git",
    "deleted-in-cpi": "Gone from CPI",
}


def esc(value):
    return html.escape("" if value is None else str(value))


def fmt_odata_date(value):
    """Turn '/Date(1712345678000)/' or an ISO string into a readable UTC stamp."""
    if not value:
        return "—"
    match = re.search(r"/Date\((\d+)", str(value))
    if match:
        ts = int(match.group(1)) / 1000
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return esc(value)


def fmt_iso(value):
    if not value:
        return "—"
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return esc(value)


def version_cell(art):
    git_v = esc(art.get("gitVersion") or "—")
    cpi_v = esc(art.get("cpiVersion") or "—")
    changed = art.get("status") != "up-to-date"
    cls = "delta changed" if changed else "delta"
    return (
        f'<span class="{cls}">'
        f'<span class="v git">{git_v}</span>'
        f'<span class="arrow" aria-hidden="true">&rarr;</span>'
        f'<span class="v cpi">{cpi_v}</span>'
        f"</span>"
    )


def render(data):
    packages = data.get("packages", [])
    total_pkg = len(packages)
    total_art = sum(len(p.get("artifacts", [])) for p in packages)
    drift_pkg = sum(1 for p in packages if not p.get("upToDate"))
    in_sync_pkg = total_pkg - drift_pkg
    all_ok = data.get("allUpToDate", False) and total_pkg > 0
    generated = fmt_iso(data.get("generatedAt"))

    if total_pkg == 0:
        verdict_word = "No packages tracked yet"
        verdict_sub = "Run the download workflow to add a package to this board."
        verdict_state = "empty"
    elif all_ok:
        verdict_word = "Everything is in sync"
        verdict_sub = f"All {total_art} artifact(s) across {total_pkg} package(s) match CPI."
        verdict_state = "ok"
    else:
        verdict_word = f"{drift_pkg} package(s) need attention"
        verdict_sub = "Some artifacts in git no longer match the active version in CPI."
        verdict_state = "warn"

    cards = []
    for pkg in packages:
        state = "ok" if pkg.get("upToDate") else "warn"
        rows = []
        for art in pkg.get("artifacts", []):
            status = art.get("status", "outdated")
            rows.append(
                "<tr>"
                f'<td class="name">{esc(art.get("name"))}'
                f'<span class="id">{esc(art.get("id"))}</span></td>'
                f'<td class="ver">{version_cell(art)}</td>'
                f'<td class="st"><span class="pill {esc(status)}">'
                f'{esc(STATUS_LABEL.get(status, status))}</span></td>'
                "</tr>"
            )
        if not rows:
            rows.append('<tr><td colspan="3" class="muted">No artifacts recorded.</td></tr>')

        cards.append(f"""
        <article class="card {state}">
          <header class="card-head">
            <h2>{esc(pkg.get("packageId"))}</h2>
            <span class="badge {state}">{'In sync' if pkg.get('upToDate') else 'Drift'}</span>
          </header>
          <dl class="meta">
            <div><dt>CPI package version</dt><dd>{esc(pkg.get("cpiPackageVersion") or "—")}</dd></div>
            <div><dt>CPI last modified</dt><dd>{fmt_odata_date(pkg.get("cpiModifiedDate"))}</dd></div>
            <div><dt>Last pulled to git</dt><dd>{fmt_iso(pkg.get("syncedAt"))}</dd></div>
          </dl>
          <table>
            <thead><tr><th>Artifact</th><th>git &rarr; CPI</th><th>Status</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </article>""")

    return TEMPLATE.format(
        verdict_state=verdict_state,
        verdict_word=esc(verdict_word),
        verdict_sub=esc(verdict_sub),
        total_pkg=total_pkg,
        in_sync_pkg=in_sync_pkg,
        drift_pkg=drift_pkg,
        total_art=total_art,
        generated=generated,
        cards="".join(cards) if cards else '<p class="muted empty">Nothing to show yet.</p>',
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPI Sync Status</title>
<style>
  :root {{
    --bg: #f5f6f8; --panel: #ffffff; --ink: #16181f; --muted: #6a7180;
    --line: #e4e7ec; --accent: #4b3ff2;
    --ok: #0f7a52; --ok-bg: #e5f4ee; --warn: #a65a00; --warn-bg: #fbeede;
    --gone: #b42318; --gone-bg: #fdeceb;
    --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
    line-height: 1.5; -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 1000px; margin: 0 auto; padding: 0 20px 64px; }}

  .top {{ background: #14161d; color: #fff; }}
  .top .wrap {{ display: flex; align-items: baseline; justify-content: space-between;
    padding-top: 22px; padding-bottom: 22px; flex-wrap: wrap; gap: 8px; }}
  .brand {{ font-weight: 700; letter-spacing: -0.02em; font-size: 18px; }}
  .brand span {{ color: #8b8fff; }}
  .gen {{ color: #a8adba; font-size: 13px; font-family: var(--mono); }}

  .verdict {{ margin-top: 28px; padding: 22px 24px; border-radius: 14px; background: var(--panel);
    border: 1px solid var(--line); display: flex; gap: 16px; align-items: center; }}
  .dot {{ width: 14px; height: 14px; border-radius: 50%; flex: none; margin-top: 6px; }}
  .verdict.ok .dot {{ background: var(--ok); }}
  .verdict.warn .dot {{ background: var(--warn); }}
  .verdict.empty .dot {{ background: var(--muted); }}
  .verdict h1 {{ margin: 0; font-size: 24px; letter-spacing: -0.02em; }}
  .verdict p {{ margin: 2px 0 0; color: var(--muted); font-size: 15px; }}

  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }}
  .stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }}
  .stat .n {{ font-size: 26px; font-weight: 700; letter-spacing: -0.03em; }}
  .stat .l {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
  .stat.warn .n {{ color: var(--warn); }}
  .stat.ok .n {{ color: var(--ok); }}

  .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    margin-top: 20px; overflow: hidden; }}
  .card.warn {{ border-color: #f0d9b8; }}
  .card-head {{ display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; border-bottom: 1px solid var(--line); }}
  .card-head h2 {{ margin: 0; font-size: 17px; letter-spacing: -0.01em; font-family: var(--mono); }}
  .badge {{ font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; }}
  .badge.ok {{ background: var(--ok-bg); color: var(--ok); }}
  .badge.warn {{ background: var(--warn-bg); color: var(--warn); }}

  .meta {{ display: flex; flex-wrap: wrap; gap: 24px; margin: 0; padding: 14px 20px;
    border-bottom: 1px solid var(--line); }}
  .meta div {{ display: flex; flex-direction: column; }}
  .meta dt {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
  .meta dd {{ margin: 2px 0 0; font-size: 14px; font-family: var(--mono); }}

  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 11px 20px; font-size: 14px; border-bottom: 1px solid var(--line); }}
  th {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  td.name {{ font-weight: 500; }}
  td.name .id {{ display: block; font-size: 12px; color: var(--muted); font-family: var(--mono); }}
  .delta {{ font-family: var(--mono); font-size: 13px; display: inline-flex; align-items: center; gap: 8px; }}
  .delta .arrow {{ color: var(--muted); }}
  .delta.changed .cpi {{ color: var(--warn); font-weight: 700; }}
  .delta .v {{ padding: 1px 6px; border-radius: 5px; background: #f1f2f5; }}

  .pill {{ font-size: 12px; font-weight: 600; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }}
  .pill.up-to-date {{ background: var(--ok-bg); color: var(--ok); }}
  .pill.outdated {{ background: var(--warn-bg); color: var(--warn); }}
  .pill.missing-in-git {{ background: #eef0ff; color: var(--accent); }}
  .pill.deleted-in-cpi {{ background: var(--gone-bg); color: var(--gone); }}

  .muted {{ color: var(--muted); }}
  .empty {{ padding: 40px 0; text-align: center; }}

  @media (max-width: 640px) {{
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
    .meta {{ gap: 16px; }}
  }}
  @media (prefers-reduced-motion: no-preference) {{
    .card {{ transition: border-color .2s ease; }}
  }}
</style>
</head>
<body>
  <div class="top"><div class="wrap">
    <div class="brand">CPI Sync <span>Status</span></div>
    <div class="gen">generated {generated}</div>
  </div></div>

  <main class="wrap">
    <section class="verdict {verdict_state}">
      <span class="dot"></span>
      <div><h1>{verdict_word}</h1><p>{verdict_sub}</p></div>
    </section>

    <section class="stats">
      <div class="stat"><div class="n">{total_pkg}</div><div class="l">Packages</div></div>
      <div class="stat ok"><div class="n">{in_sync_pkg}</div><div class="l">In sync</div></div>
      <div class="stat warn"><div class="n">{drift_pkg}</div><div class="l">Drifted</div></div>
      <div class="stat"><div class="n">{total_art}</div><div class="l">Artifacts</div></div>
    </section>

    {cards}
  </main>
</body>
</html>
"""


def main():
    if not os.path.exists(DATA_FILE):
        print(f"::error::{DATA_FILE} not found. Run check_drift.py first.", file=sys.stderr)
        sys.exit(1)
    with open(DATA_FILE) as handle:
        data = json.load(handle)
    os.makedirs("docs", exist_ok=True)
    with open(OUT_FILE, "w") as handle:
        handle.write(render(data))
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
