"""output/index.html、Phase別HTML、output/assets/ を再生成するスクリプト。

使い方:
    python gen_index.py

出力先:
    output/index.html
    output/phase1.html
    output/phase2.html
    output/phase3.html
    output/assets/phase1-pages.js
    output/assets/phase1-components.js
    output/assets/phase1.css
"""

from __future__ import annotations

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
ASSETS_DIR = OUTPUT_DIR / "assets"

# 市区町村マスタ（コード → 名称）― シナリオ生成対象41市区町村
_CITY_NAMES: dict[str, str] = {
    "08201": "水戸市",
    "08202": "日立市",
    "08203": "土浦市",
    "08204": "古河市",
    "08205": "石岡市",
    "08207": "結城市",
    "08208": "龍ケ崎市",
    "08210": "下妻市",
    "08211": "常総市",
    "08212": "常陸太田市",
    "08214": "高萩市",
    "08215": "北茨城市",
    "08216": "笠間市",
    "08217": "取手市",
    "08219": "牛久市",
    "08220": "つくば市",
    "08221": "ひたちなか市",
    "08223": "潮来市",
    "08224": "守谷市",
    "08225": "常陸大宮市",
    "08226": "那珂市",
    "08227": "筑西市",
    "08228": "坂東市",
    "08229": "稲敷市",
    "08230": "かすみがうら市",
    "08231": "桜川市",
    "08233": "行方市",
    "08234": "鉾田市",
    "08235": "つくばみらい市",
    "08236": "小美玉市",
    "08302": "茨城町",
    "08309": "大洗町",
    "08310": "城里町",
    "08364": "大子町",
    "08442": "美浦村",
    "08443": "阿見町",
    "08447": "河内町",
    "08521": "八千代町",
    "08542": "五霞町",
    "08546": "境町",
    "08564": "利根町",
}

# A31a境界内0件のため対象外（3市町村）
_UNAVAILABLE_CITIES: list[dict[str, str]] = [
    {"title": "鹿嶋市", "meta": "08222", "reason": "沿岸・汽水域のため河川洪水想定なし"},
    {"title": "神栖市", "meta": "08232", "reason": "利根川河口・沿岸。利根川系データ未収録"},
    {"title": "東海村", "meta": "08341", "reason": "海岸段丘台地。那珂川浸水域が市境外止まり"},
]


def _city_entries() -> list[dict]:
    cities_dir = OUTPUT_DIR / "scenario_cities"
    entries = []
    for code in sorted(_CITY_NAMES):
        html = cities_dir / code / "scenario_route_simulation.html"
        if html.exists():
            entries.append({
                "title": _CITY_NAMES[code],
                "meta": code,
                "href": f"scenario_cities/{code}/scenario_route_simulation.html",
            })
    return entries


def _js_obj(d: dict) -> str:
    fields = ", ".join(f'{k}: "{v}"' for k, v in d.items())
    return "{ " + fields + " }"


def write_pages_js(entries: list[dict]) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    route_times = [
        ("t0", "2015-09-10 18:00"),
        ("t1", "2015-09-11 06:00"),
        ("t2", "2015-09-11 18:00"),
        ("t3", "2015-09-12 06:00"),
        ("t4", "2015-09-12 18:00"),
        ("t5", "2015-09-13 06:00"),
        ("t6", "2015-09-13 18:00"),
        ("t7", "2015-09-16 10:20"),
    ]
    routes_js = "\n".join(
        f'    {{ title: "{t}", meta: "{m}", href: "routes/evacuation_routes_{t}.html" }},'
        for t, m in route_times
    )
    cities_js = "\n".join(
        f'    {{ title: "{e["title"]}", meta: "{e["meta"]}", href: "{e["href"]}" }},'
        for e in entries
    )
    unavailable_js = "\n".join(
        f'    {{ title: "{e["title"]}", meta: "{e["meta"]}", reason: "{e["reason"]}" }},'
        for e in _UNAVAILABLE_CITIES
    )

    content = f"""window.RESULT_PAGES = {{
  overview: [
    {{ title: "道路ネットワーク", meta: "常総市道路NW", href: "network/joso_network_map.html" }},
    {{ title: "浸水時系列マップ", meta: "8時点の浸水範囲", href: "flood/flood_timeline_map.html" }},
  ],
  routes: [
{routes_js}
  ],
  scenario: [
    {{ title: "常総市シミュレーション（参考）", meta: "常総市のみ対象。県内拡張版は上の統合版を使用", href: "scenario_v2/scenario_route_simulation.html" }},
  ],
  unified: [
    {{ title: "茨城県41市区町村 統合シミュレーション", meta: "県内拡張版。まずはこちらから確認", href: "unified/scenario_route_simulation.html", primary: true }},
  ],
  phase2Excel: [
    {{ title: "Phase 2評価結果 Excel", meta: "評価CSV6種類を1つのExcelブックへ統合", href: "sumo/evaluation/phase2_results_excel.xlsx", primary: true, download: true }},
    {{ title: "市区町村別避難結果サマリCSV", meta: "Phase 2全域拡張の市区町村別集計", href: "sumo/evaluation/evacuation_summary_by_municipality.csv", download: true }},
    {{ title: "Phase 1 / Phase 2 全域比較CSV", meta: "静的入力規模と動的SUMO結果を市区町村別に整理", href: "sumo/evaluation/phase1_phase2_region_comparison.csv", download: true }},
    {{ title: "避難結果サマリCSV", meta: "small / 1/10 / full の到着・未到着・逃げ遅れ", href: "sumo/evaluation/evacuation_summary.csv", download: true }},
    {{ title: "試行設定比較CSV", meta: "small / 10pct / full の車両数・到着率・避難完了時間", href: "sumo/evaluation/trial_settings_comparison.csv", download: true }},
    {{ title: "混雑ログCSV", meta: "60秒間隔のアクティブ台数・平均速度・停止台数", href: "sumo/evaluation/congestion_log.csv", download: true }},
    {{ title: "主要避難路別混雑集計CSV", meta: "R294・R354・R357・常総IC接続部の平均速度・低速率", href: "sumo/evaluation/major_route_congestion_summary.csv", download: true }},
    {{ title: "Phase 1 / Phase 2 比較CSV", meta: "常総市の静的到達不可と動的逃げ遅れを整理", href: "sumo/evaluation/phase1_phase2_comparison.csv", download: true }},
  ],
  phase2Animation: [
    {{ title: "SUMO走行アニメーション", meta: "FCD出力ベースの車両移動・道路閉鎖可視化", href: "sumo/viz/sumo_viz.html", primary: true }},
    {{ title: "Phase 2 全域SUMO結果", meta: "41市区町村のsmall/10pct/full方針を一覧表示", href: "sumo/regions/index.html" }},
  ],
  phase3: [],
  cities: [
{cities_js}
  ],
  unavailable: [
{unavailable_js}
  ],
}};
"""
    (ASSETS_DIR / "phase1-pages.js").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'phase1-pages.js'}  ({len(entries)} 市区町村)")


def write_components_js() -> None:
    content = """(function () {
  function createCard(page) {
    const link = document.createElement("a");
    link.className = page.primary ? "card-link card-link-primary" : "card-link";
    link.href = page.href;
    if (page.download) link.setAttribute("download", "");
    const title = document.createElement("span");
    title.className = "card-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "card-meta";
    meta.textContent = page.meta;
    link.append(title, meta);
    return link;
  }

  function createRouteItem(page) {
    const link = document.createElement("a");
    link.className = "route-link";
    link.href = page.href;
    const title = document.createElement("span");
    title.className = "route-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "route-meta";
    meta.textContent = page.meta;
    link.append(title, meta);
    return link;
  }

  function createCityCard(page) {
    const link = document.createElement("a");
    link.className = "city-card-link";
    link.href = page.href;
    const title = document.createElement("span");
    title.className = "city-card-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "city-card-meta";
    meta.textContent = page.meta;
    link.append(title, meta);
    return link;
  }

  function createUnavailableItem(page) {
    const item = document.createElement("li");
    item.className = "unavailable-item";
    const title = document.createElement("span");
    title.className = "unavailable-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "unavailable-meta";
    meta.textContent = `${page.meta} / ${page.reason}`;
    item.append(title, meta);
    return item;
  }

  function renderList(targetId, pages, createItem) {
    const target = document.getElementById(targetId);
    if (!target) return;
    target.replaceChildren(...pages.map(createItem));
  }

  function normalizeText(value) {
    return String(value || "").toLowerCase().replace(/\\s+/g, "");
  }

  function renderCities(pages) {
    const target = document.getElementById("city-links");
    if (!target) return;

    const search = document.getElementById("city-search");
    const select = document.getElementById("city-select");
    const count = document.getElementById("city-count");

    if (select && select.options.length === 0) {
      const all = document.createElement("option");
      all.value = "";
      all.textContent = "すべての市区町村";
      select.appendChild(all);
      pages.forEach(function (page) {
        const option = document.createElement("option");
        option.value = page.meta;
        option.textContent = `${page.title}（${page.meta}）`;
        select.appendChild(option);
      });
    }

    function applyFilter() {
      const query = normalizeText(search ? search.value : "");
      const selected = select ? select.value : "";
      const filtered = pages.filter(function (page) {
        const haystack = normalizeText(`${page.title}${page.meta}`);
        return (!selected || page.meta === selected) && (!query || haystack.includes(query));
      });
      target.replaceChildren(...filtered.map(createCityCard));
      if (count) count.textContent = `${filtered.length} / ${pages.length} 件`;
    }

    if (search) search.addEventListener("input", applyFilter);
    if (select) select.addEventListener("change", applyFilter);
    applyFilter();
  }

  window.addEventListener("DOMContentLoaded", function () {
    const pages = window.RESULT_PAGES;
    if (!pages) return;
    renderList("overview-links", pages.overview, createCard);
    renderList("route-links", pages.routes, createRouteItem);
    renderList("scenario-links", pages.scenario || [], createCard);
    renderList("unified-links", pages.unified || [], createCard);
    renderList("phase2-excel-links", pages.phase2Excel || [], createCard);
    renderList("phase2-animation-links", pages.phase2Animation || [], createCard);
    renderList("phase3-links", pages.phase3 || [], createCard);
    renderCities(pages.cities || []);
    renderList("unavailable-links", pages.unavailable || [], createUnavailableItem);
  });
})();
"""
    (ASSETS_DIR / "phase1-components.js").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'phase1-components.js'}")


def write_css() -> None:
    content = """:root {
  color-scheme: light;
  --bg: #ffffff;
  --text: #1f2933;
  --muted: #6b7280;
  --line: #d9dee5;
  --surface: #f8fafc;
  --surface-hover: #f2f5f8;
  --accent: #2563eb;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: "Yu Gothic", "Meiryo", system-ui, sans-serif;
  line-height: 1.6;
}
a { color: inherit; text-decoration: none; }
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  max-width: 1040px;
  margin: 0 auto;
  padding: 40px 24px 24px;
  border-bottom: 1px solid var(--line);
}
.eyebrow, .updated { margin: 0; color: var(--muted); font-size: 13px; }
h1 { margin: 4px 0 0; font-size: 28px; font-weight: 700; letter-spacing: 0; }
.page-shell { max-width: 1040px; margin: 0 auto; padding: 28px 24px 48px; }
.phase-nav { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 28px; }
.phase-nav a {
  display: flex;
  flex-direction: column;
  min-height: 78px;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
}
.phase-nav a:hover, .phase-nav a:focus-visible { background: var(--surface-hover); border-color: var(--accent); outline: none; }
.phase-nav-title { font-weight: 700; font-size: 15px; }
.phase-nav-meta { margin-top: 4px; color: var(--muted); font-size: 12px; }
.section + .section { margin-top: 36px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
h2 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: 0; }
.section-note { margin: 0 0 12px; color: var(--muted); font-size: 14px; }
.card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.reference-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
.reference-block { min-width: 0; }
.reference-title { margin: 0 0 8px; font-size: 14px; color: var(--muted); font-weight: 700; }
.card-link, .route-link {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  transition: background-color 120ms ease, border-color 120ms ease;
}
.card-link:hover, .route-link:hover,
.card-link:focus-visible, .route-link:focus-visible {
  background: var(--surface-hover);
  border-color: var(--accent);
  outline: none;
}
.card-link { display: flex; flex-direction: column; min-height: 92px; padding: 18px; }
.card-link-primary { border-color: #93c5fd; background: #eff6ff; }
.card-title { font-size: 17px; font-weight: 700; }
.card-meta, .route-meta { color: var(--muted); font-size: 13px; }
.card-meta { margin-top: 6px; }
.route-list { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.route-link { display: flex; flex-direction: column; min-height: 76px; padding: 14px; }
.route-title { font-size: 16px; font-weight: 700; }
.route-meta { margin-top: 3px; }
.city-tools { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(220px, 1fr) auto; gap: 10px; align-items: end; margin-bottom: 12px; }
.city-tool { display: flex; flex-direction: column; gap: 4px; color: var(--muted); font-size: 12px; }
.city-search, .city-select {
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  padding: 8px 10px;
  font: inherit;
}
.city-search:focus, .city-select:focus { border-color: var(--accent); outline: none; }
.city-count { color: var(--muted); font-size: 13px; white-space: nowrap; }
.city-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.city-card-link {
  display: flex;
  flex-direction: column;
  min-height: 64px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  transition: background-color 120ms ease, border-color 120ms ease;
}
.city-card-link:hover, .city-card-link:focus-visible {
  background: var(--surface-hover);
  border-color: var(--accent);
  outline: none;
}
.city-card-title { font-size: 14px; font-weight: 700; }
.city-card-meta { margin-top: 2px; color: var(--muted); font-size: 12px; }
.unavailable-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 0; padding: 0; list-style: none; }
.unavailable-item { min-height: 58px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
.unavailable-title { display: block; font-size: 14px; font-weight: 700; }
.unavailable-meta { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; }
.summary-stats { display: flex; gap: 16px; align-items: center; padding: 16px 20px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); margin-bottom: 28px; }
.stat-item { display: flex; flex-direction: column; align-items: center; min-width: 52px; }
.stat-value { font-size: 28px; font-weight: 700; color: var(--accent); line-height: 1; }
.stat-label { font-size: 11px; color: var(--muted); margin-top: 2px; }
.stat-text { flex: 1; color: var(--muted); font-size: 13px; border-left: 1px solid var(--line); padding-left: 16px; margin-left: 4px; }
.phase-card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-bottom: 28px; }
.phase-card {
  display: flex;
  flex-direction: column;
  min-height: 260px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  transition: background-color 120ms ease, border-color 120ms ease;
}
.phase-card:hover, .phase-card:focus-visible { background: var(--surface-hover); border-color: var(--accent); outline: none; }
.phase-card-title { font-size: 20px; font-weight: 700; }
.phase-status { display: inline-flex; width: fit-content; margin-top: 8px; padding: 2px 8px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-size: 12px; }
.phase-card-meta { margin: 12px 0 0; color: var(--muted); font-size: 13px; }
.phase-card-list { margin: 14px 0 0; padding-left: 18px; font-size: 13px; color: var(--text); }
.phase-card-list li + li { margin-top: 4px; }
.header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.github-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
  transition: background-color 120ms ease, border-color 120ms ease;
}
.github-link:hover, .github-link:focus-visible { background: var(--surface-hover); border-color: var(--accent); outline: none; }
.github-icon { width: 16px; height: 16px; fill: currentColor; flex-shrink: 0; }
.back-link { display: inline-flex; margin-bottom: 16px; color: var(--accent); font-size: 13px; font-weight: 700; }
.phase-lead { margin: 0 0 20px; color: var(--muted); font-size: 14px; }
.detail-list { margin: 8px 0 0; padding-left: 18px; color: var(--text); font-size: 14px; }
.detail-list li + li { margin-top: 4px; }
@media (max-width: 760px) {
  .page-header { display: block; padding-top: 28px; }
  .updated { margin-top: 12px; }
  .phase-nav, .phase-card-grid, .card-grid, .route-list, .city-grid, .city-tools, .unavailable-list { grid-template-columns: 1fr; }
  .city-count { white-space: normal; }
  .summary-stats { flex-wrap: wrap; }
  .stat-text { border-left: 0; padding-left: 0; margin-left: 0; border-top: 1px solid var(--line); padding-top: 10px; width: 100%; }
}
"""
    (ASSETS_DIR / "phase1.css").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'phase1.css'}")


def _page_header(title: str, subtitle: str, label: str) -> str:
    return f"""  <header class="page-header">
    <div>
      <p class="eyebrow">{subtitle}</p>
      <h1>{title}</h1>
    </div>
    <p class="updated">{label}</p>
  </header>"""


def _phase_nav(active: str | None = None) -> str:
    def link(phase: str, title: str, meta: str, href: str) -> str:
        current = ' aria-current="page"' if active == phase else ""
        return f"""      <a href="{href}"{current}>
        <span class="phase-nav-title">{title}</span>
        <span class="phase-nav-meta">{meta}</span>
      </a>"""

    return "\n".join([
        '    <nav class="phase-nav" aria-label="Phase別成果物">',
        link("phase1", "Phase 1", "浸水・閉鎖道路・避難ルート確認", "phase1.html"),
        link("phase2", "Phase 2", "SUMO自家用車避難シミュレーション", "phase2.html"),
        link("phase3", "Phase 3", "デマンド交通バス比較・感度分析", "phase3.html"),
        "    </nav>",
    ])


def _html_doc(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="assets/phase1.css">
  <script src="assets/phase1-pages.js" defer></script>
  <script src="assets/phase1-components.js" defer></script>
</head>
<body>
{body}
</body>
</html>
"""


_GITHUB_URL = "https://github.com/23f302020/joso-evacuation-simulation"


def write_index_html(n_cities: int) -> None:
    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>研究成果物トップページ</title>
  <link rel="stylesheet" href="assets/phase1.css">
</head>
<body>
  <header class="page-header">
    <div>
      <p class="eyebrow">2015 鬼怒川氾濫 / 茨城県</p>
      <h1>研究成果物トップページ</h1>
    </div>
    <div class="header-right">
      <p class="updated">Phase別入口</p>
      <a class="github-link" href="{_GITHUB_URL}" target="_blank" rel="noopener noreferrer">
        <svg class="github-icon" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        GitHub
      </a>
    </div>
  </header>

  <main class="page-shell">
    <div class="summary-stats" aria-label="研究概要">
      <div class="stat-item"><span class="stat-value">{n_cities}</span><span class="stat-label">市区町村</span></div>
      <div class="stat-item"><span class="stat-value">3</span><span class="stat-label">対象外</span></div>
      <div class="stat-item"><span class="stat-value">8</span><span class="stat-label">時点</span></div>
      <div class="stat-item stat-text">Phase 1は静的な避難ルート、Phase 2はSUMOによる動的交通流、Phase 3はデマンド交通バス比較の予定です。</div>
    </div>

    <section class="phase-card-grid" aria-label="Phase別ページ">
      <a class="phase-card" href="phase1.html">
        <span class="phase-card-title">Phase 1</span>
        <span class="phase-status">実装済み</span>
        <span class="phase-card-meta">浸水想定区域と道路閉鎖を使い、閉鎖道路を除いた避難ルートを確認する静的シミュレーションです。</span>
        <ul class="phase-card-list">
          <li>茨城県41市区町村の統合シミュレーション</li>
          <li>市区町村別シミュレーションHTML</li>
          <li>常総市の実データ版・時点別避難ルート</li>
        </ul>
      </a>
      <a class="phase-card" href="phase2.html">
        <span class="phase-card-title">Phase 2</span>
        <span class="phase-status">実装済み</span>
        <span class="phase-card-meta">SUMO/TraCIを用いて、自家用車避難の到着・未到着・停止・主要避難路の混雑を確認する動的シミュレーションです。</span>
        <ul class="phase-card-list">
          <li>常総市 small / 1/10 / 全量試行</li>
          <li>SUMO走行アニメーションと評価CSV</li>
          <li>41市区町村へのPhase 2全域拡張結果</li>
        </ul>
      </a>
      <a class="phase-card" href="phase3.html">
        <span class="phase-card-title">Phase 3</span>
        <span class="phase-status">未実装</span>
        <span class="phase-card-meta">Phase 2の自家用車避難を基準に、デマンド交通バスを導入した場合の比較を行う予定のPhaseです。</span>
        <ul class="phase-card-list">
          <li>バス台数・定員・運行範囲の仕様化</li>
          <li>シナリオBの運行ロジック実装</li>
          <li>自家用車のみとの比較・考察</li>
        </ul>
      </a>
    </section>
  </main>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[write] {OUTPUT_DIR / 'index.html'}")


def write_phase1_html(n_cities: int) -> None:
    body = f"""{_page_header("Phase 1：避難ルート確認", "浸水想定区域 / 閉鎖道路 / 静的避難ルート", f"{n_cities}市区町村")}

  <main class="page-shell">
    <a class="back-link" href="index.html">トップページへ戻る</a>
{_phase_nav("phase1")}
    <p class="phase-lead">Phase 1では、浸水想定区域から閉鎖道路を抽出し、閉鎖道路を除いた道路ネットワーク上で避難所までのルートを確認します。</p>

    <section class="section" aria-labelledby="unified-heading">
      <div class="section-heading">
        <h2 id="unified-heading">茨城県統合シミュレーション（{n_cities}市区町村）</h2>
      </div>
      <p class="section-note">県内拡張版の主成果物です。クリック地点に応じて対象市区町村のデータを読み込みます。</p>
      <div id="unified-links" class="card-grid"></div>
    </section>

    <section class="section" aria-labelledby="cities-heading">
      <div class="section-heading">
        <h2 id="cities-heading">市区町村別シミュレーション</h2>
      </div>
      <p class="section-note">特定の市区町村だけを確認したい場合はこちらを使用します。</p>
      <div class="city-tools" aria-label="市区町村リンクの絞り込み">
        <label class="city-tool" for="city-search">
          検索
          <input class="city-search" id="city-search" type="search" placeholder="例：水戸市、08201">
        </label>
        <label class="city-tool" for="city-select">
          市区町村選択
          <select class="city-select" id="city-select"></select>
        </label>
        <span class="city-count" id="city-count"></span>
      </div>
      <div id="city-links" class="city-grid"></div>
    </section>

    <section class="section" aria-labelledby="scenario-heading">
      <div class="section-heading">
        <h2 id="scenario-heading">常総市単独シミュレーション（参考）</h2>
      </div>
      <p class="section-note">県内拡張前の常総市単独成果物です。常総市以外をクリックすると対応地域外として扱います。</p>
      <div id="scenario-links" class="card-grid"></div>
    </section>

    <section class="section" aria-labelledby="unavailable-heading">
      <div class="section-heading">
        <h2 id="unavailable-heading">対象外市町村（3市町村）</h2>
      </div>
      <p class="section-note">A31a浸水想定区域データが境界内に存在しないため、シナリオ生成対象外です。</p>
      <ul id="unavailable-links" class="unavailable-list"></ul>
    </section>

    <section class="section" aria-labelledby="reference-heading">
      <div class="section-heading">
        <h2 id="reference-heading">参考：常総市実データ版</h2>
      </div>
      <p class="section-note">道路ネットワーク、浸水時系列、時点別避難ルートを確認します。</p>
      <div class="reference-grid">
        <div class="reference-block">
          <h3 class="reference-title">地図</h3>
          <div id="overview-links" class="card-grid"></div>
        </div>
        <div class="reference-block">
          <h3 class="reference-title">避難ルート</h3>
          <div id="route-links" class="route-list"></div>
        </div>
      </div>
    </section>
  </main>
"""
    (OUTPUT_DIR / "phase1.html").write_text(_html_doc("Phase 1：避難ルート確認", body), encoding="utf-8")
    print(f"[write] {OUTPUT_DIR / 'phase1.html'}")


def write_phase2_html() -> None:
    body = f"""{_page_header("Phase 2：SUMO自家用車避難", "交通流シミュレーション / TraCI / 評価CSV", "実装済み")}

  <main class="page-shell">
    <a class="back-link" href="index.html">トップページへ戻る</a>
{_phase_nav("phase2")}
    <p class="phase-lead">Phase 2では、Phase 1の閉鎖道路と避難需要をSUMOネットワークへ接続し、自家用車のみの避難を動的に評価します。</p>

    <section class="section" aria-labelledby="phase2-contents-heading">
      <div class="section-heading">
        <h2 id="phase2-contents-heading">確認できる内容</h2>
      </div>
      <ul class="detail-list">
        <li>常総市のsmall / 1/10 / 全量試行における到着・未到着・逃げ遅れ候補</li>
        <li>60秒間隔のアクティブ車両数、平均速度、停止台数による混雑推移</li>
        <li>国道294号、国道・県道354号、県道357号、常総IC接続部の主要避難路別混雑</li>
        <li>41市区町村へ拡張したPhase 2 SUMO入力・結果一覧</li>
      </ul>
    </section>

    <section class="section" aria-labelledby="phase2-excel-heading">
      <div class="section-heading">
        <h2 id="phase2-excel-heading">Excelでダウンロードする成果物</h2>
      </div>
      <p class="section-note">統合Excelブックと、Excelで開ける元CSVをまとめています。表・考察・卒論転記に使う成果物です。</p>
      <div id="phase2-excel-links" class="card-grid"></div>
    </section>

    <section class="section" aria-labelledby="phase2-animation-heading">
      <div class="section-heading">
        <h2 id="phase2-animation-heading">アニメーションで確認できる成果物</h2>
      </div>
      <p class="section-note">SUMOの車両移動、道路閉鎖、対象市区町村別の実行結果を画面で確認します。</p>
      <div id="phase2-animation-links" class="card-grid"></div>
    </section>
  </main>
"""
    (OUTPUT_DIR / "phase2.html").write_text(_html_doc("Phase 2：SUMO自家用車避難", body), encoding="utf-8")
    print(f"[write] {OUTPUT_DIR / 'phase2.html'}")


def write_phase3_html() -> None:
    evaluation = OUTPUT_DIR / "sumo" / "regions" / "08211" / "evaluation"
    band = json.loads((evaluation / "phase3r_e1_band_summary.json").read_text(encoding="utf-8"))
    s10 = json.loads((evaluation / "phase3_s10_band_summary.json").read_text(encoding="utf-8"))
    raw_signs = band["raw_sign_counts"]
    conservative_signs = band["conservative_sign_counts"]
    s10_raw_signs = s10["raw_sign_counts"]
    s10_conservative_signs = s10["conservative_sign_counts"]
    body = f"""{_page_header("Phase 3：デマンド交通バス比較", "バス活用シナリオ / 比較評価", "実装・評価済み")}

  <main class="page-shell">
    <a class="back-link" href="index.html">トップページへ戻る</a>
{_phase_nav("phase3")}
    <p class="phase-lead">自家用車のみのA側3runと、バス活用B側5runを比較しました。完了率差の帯はゼロをまたぎ、本モデルの分解能では方向差を検出できませんでした。</p>

    <section class="section" aria-labelledby="phase3-plan-heading">
      <div class="section-heading">
        <h2 id="phase3-plan-heading">評価結果</h2>
      </div>
      <ul class="detail-list">
        <li>Type3/4完了率のraw点推定：{band['raw_point_delta_percentage_points']:+.2f}%pt、帯：{band['raw_delta_min_percentage_points']:+.2f}〜{band['raw_delta_max_percentage_points']:+.2f}%pt</li>
        <li>保守点推定：{band['conservative_point_delta_percentage_points']:+.2f}%pt、帯：{band['conservative_delta_min_percentage_points']:+.2f}〜{band['conservative_delta_max_percentage_points']:+.2f}%pt</li>
        <li>15組合せはrawで正{raw_signs['positive']}・負{raw_signs['negative']}、保守で正{conservative_signs['positive']}・負{conservative_signs['negative']}となり、いずれも符号は非一貫</li>
        <li>10台感度はrawで正{s10_raw_signs['positive']}・負{s10_raw_signs['negative']}、保守で正{s10_conservative_signs['positive']}・負{s10_conservative_signs['negative']}。S10#4はraw 102.01%・保守97.15%を併記</li>
      </ul>
    </section>

    <section class="section" aria-labelledby="phase3-links-heading">
      <div class="section-heading">
        <h2 id="phase3-links-heading">Phase 3成果物</h2>
      </div>
      <div class="card-grid">
        <a class="result-card" href="sumo/viz/phase3_viz.html"><strong>結果可視化・交通アニメーション</strong><span>不確実性帯、二峰性、バスと車両の移動</span></a>
        <a class="result-card" href="sumo/regions/08211/evaluation/phase3_ab_comparison.csv"><strong>A/B比較CSV</strong><span>raw・保守帯と15組合せ符号</span></a>
        <a class="result-card" href="sumo/regions/08211/evaluation/phase3r_e1_15_combination_signs.csv"><strong>15組合せ符号表</strong><span>完了率実値ベース</span></a>
        <a class="result-card" href="sumo/regions/08211/evaluation/phase3_s10_15_combination_signs.csv"><strong>10台感度符号表</strong><span>5seed×A側3run</span></a>
      </div>
    </section>
  </main>
"""
    (OUTPUT_DIR / "phase3.html").write_text(
        _html_doc("Phase 3：デマンド交通バス比較", body),
        encoding="utf-8",
        newline="\n",
    )
    print(f"[write] {OUTPUT_DIR / 'phase3.html'}")


def main() -> None:
    entries = _city_entries()
    write_pages_js(entries)
    write_components_js()
    write_css()
    write_index_html(len(entries))
    write_phase1_html(len(entries))
    write_phase2_html()
    write_phase3_html()
    print(f"\n完了: {len(entries)} 市区町村を Phase別HTML に登録しました")


if __name__ == "__main__":
    main()
