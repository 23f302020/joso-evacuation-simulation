"""output/index.html と output/assets/ を再生成するスクリプト。

使い方:
    python gen_index.py

出力先:
    output/index.html
    output/assets/phase1-pages.js
    output/assets/phase1-components.js
    output/assets/phase1.css
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
ASSETS_DIR = OUTPUT_DIR / "assets"

# 市区町村マスタ（コード → 名称）― シナリオ生成対象40市区町村
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
    "08546": "境町",
    "08564": "利根町",
}

# A31a境界内0件のため対象外（4市町村）
_UNAVAILABLE_CITIES: list[dict[str, str]] = [
    {"title": "鹿嶋市", "meta": "08222", "reason": "A31a境界内0件のため対象外"},
    {"title": "神栖市", "meta": "08232", "reason": "A31a境界内0件のため対象外"},
    {"title": "東海村", "meta": "08341", "reason": "A31a境界内0件のため対象外"},
    {"title": "五霞町", "meta": "08542", "reason": "A31a境界内0件のため対象外"},
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

    content = f"""window.PHASE1_PAGES = {{
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
    {{ title: "茨城県40市区町村 統合シミュレーション", meta: "県内拡張版。まずはこちらから確認", href: "unified/scenario_route_simulation.html", primary: true }},
  ],
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
    const pages = window.PHASE1_PAGES;
    if (!pages) return;
    renderList("overview-links", pages.overview, createCard);
    renderList("route-links", pages.routes, createRouteItem);
    renderList("scenario-links", pages.scenario || [], createCard);
    renderList("unified-links", pages.unified || [], createCard);
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
.section + .section { margin-top: 36px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
h2 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: 0; }
.section-note { margin: 0 0 12px; color: var(--muted); font-size: 14px; }
.card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
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
@media (max-width: 760px) {
  .page-header { display: block; padding-top: 28px; }
  .updated { margin-top: 12px; }
  .card-grid, .route-list, .city-grid, .city-tools, .unavailable-list { grid-template-columns: 1fr; }
  .city-count { white-space: normal; }
}
"""
    (ASSETS_DIR / "phase1.css").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'phase1.css'}")


def write_index_html(n_cities: int) -> None:
    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 1 成果物</title>
  <link rel="stylesheet" href="assets/phase1.css">
  <script src="assets/phase1-pages.js" defer></script>
  <script src="assets/phase1-components.js" defer></script>
</head>
<body>
  <header class="page-header">
    <div>
      <p class="eyebrow">2015 鬼怒川氾濫 / 茨城県</p>
      <h1>Phase 1 成果物</h1>
    </div>
    <p class="updated">HTML確認トップページ</p>
  </header>

  <main class="page-shell">
    <section class="section" aria-labelledby="overview-heading">
      <div class="section-heading">
        <h2 id="overview-heading">地図</h2>
      </div>
      <div id="overview-links" class="card-grid"></div>
    </section>

    <section class="section" aria-labelledby="routes-heading">
      <div class="section-heading">
        <h2 id="routes-heading">避難ルート（実データ版）</h2>
      </div>
      <div id="route-links" class="route-list"></div>
    </section>

    <section class="section" aria-labelledby="unified-heading">
      <div class="section-heading">
        <h2 id="unified-heading">茨城県拡張シミュレーション（36市区町村）</h2>
      </div>
      <p class="section-note">県内拡張版はこちらです。クリック地点に応じて対象市区町村のデータを読み込みます。</p>
      <div id="unified-links" class="card-grid"></div>
    </section>

    <section class="section" aria-labelledby="cities-heading">
      <div class="section-heading">
        <h2 id="cities-heading">市区町村別シミュレーション（{n_cities}市区町村）</h2>
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
      <p class="section-note">このページは常総市のみ対象です。常総市以外をクリックすると「対応地域外」と表示されます。</p>
      <div id="scenario-links" class="card-grid"></div>
    </section>

    <section class="section" aria-labelledby="unavailable-heading">
      <div class="section-heading">
        <h2 id="unavailable-heading">対象外市町村（4市町村）</h2>
      </div>
      <p class="section-note">下記はA31a浸水想定区域データが境界内に存在しないため、シナリオ生成対象外です。</p>
      <ul id="unavailable-links" class="unavailable-list"></ul>
    </section>
  </main>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[write] {OUTPUT_DIR / 'index.html'}")


def main() -> None:
    entries = _city_entries()
    write_pages_js(entries)
    write_components_js()
    write_css()
    write_index_html(len(entries))
    print(f"\n完了: {len(entries)} 市区町村を index.html に登録しました")


if __name__ == "__main__":
    main()
