"""output/unified/ に茨城県統合シミュレーションページを生成するスクリプト。

全36市区町村の data.js から都市情報を読み取り、1つの地図で
全市区町村を操作できる統合ページを output/unified/ に生成する。

使い方:
    python gen_unified.py

出力先:
    output/unified/scenario_route_simulation.html
    output/unified/assets/cities_manifest.js
    output/unified/assets/app.js
    output/unified/assets/style.css
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
UNIFIED_DIR = OUTPUT_DIR / "unified"
ASSETS_DIR = UNIFIED_DIR / "assets"
CITIES_DIR = OUTPUT_DIR / "scenario_cities"

_CITY_NAMES: dict[str, str] = {
    "08201": "水戸市",
    "08202": "日立市",
    "08203": "土浦市",
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
    "08564": "利根町",
}


def extract_city_info(code: str) -> dict | None:
    data_js = CITIES_DIR / code / "assets" / "data.js"
    if not data_js.exists():
        return None
    text = data_js.read_text(encoding="utf-8", errors="replace")

    sa_m = re.search(
        r'"supportArea":\{"label":"[^"]*","bounds":(\[\[[\d.-]+,[\d.-]+\],\[[\d.-]+,[\d.-]+\]\])',
        text,
    )
    if not sa_m:
        return None
    bounds = json.loads(sa_m.group(1))

    c_m = re.search(r'"map":\{"center":\[([\d.]+),([\d.]+)\]', text)
    if not c_m:
        return None
    center = [float(c_m.group(1)), float(c_m.group(2))]

    return {
        "code": code,
        "name": _CITY_NAMES.get(code, code),
        "bounds": bounds,
        "center": center,
    }


def write_cities_manifest(cities: list[dict]) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for city in cities:
        b = json.dumps(city["bounds"], separators=(",", ":"))
        c = json.dumps(city["center"], separators=(",", ":"))
        lines.append(
            f'  {{code:"{city["code"]}",name:"{city["name"]}",'
            f"bounds:{b},center:{c}}}"
        )
    content = "window.CITIES_MANIFEST = [\n" + ",\n".join(lines) + "\n];\n"
    (ASSETS_DIR / "cities_manifest.js").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'cities_manifest.js'}  ({len(cities)} 都市)")


def write_app_js() -> None:
    content = """\
(function () {
  var manifest = window.CITIES_MANIFEST;
  if (!manifest || !manifest.length) return;

  // ------------------------------------------------------------------ map
  var map = L.map("map", {
    maxBounds: [[34.5, 138.5], [38.5, 142.0]],
    maxBoundsViscosity: 0.7
  }).setView([36.35, 140.45], 9);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "\\u00a9 OpenStreetMap contributors \\u00a9 CARTO"
  }).addTo(map);

  // ------------------------------------------------------------------ layers (z-order: bottom -> top)
  var maskLayer    = L.layerGroup().addTo(map);
  var cityLayer    = L.layerGroup().addTo(map);
  var floodLayer   = L.geoJSON(null, {
    style: { color: "#1d4ed8", weight: 1, fillColor: "#2563eb", fillOpacity: 0.28 }
  }).addTo(map);
  var closedLayer  = L.layerGroup().addTo(map);
  var shelterLayer = L.layerGroup().addTo(map);
  var routeLayer   = L.layerGroup().addTo(map);
  var markerLayer  = L.layerGroup().addTo(map);

  // ------------------------------------------------------------------ gray mask (world box with city holes)
  var outerRing = [[34, 137], [34, 143], [39, 143], [39, 137]];
  var holes = manifest.map(function (c) {
    var s = c.bounds[0][0], w = c.bounds[0][1];
    var n = c.bounds[1][0], e = c.bounds[1][1];
    return [[s, w], [s, e], [n, e], [n, w]];
  });
  L.polygon([outerRing].concat(holes), {
    weight: 0,
    fillColor: "#1f2937",
    fillOpacity: 0.22,
    interactive: false
  }).addTo(maskLayer);

  // ------------------------------------------------------------------ city boundary rectangles
  manifest.forEach(function (city) {
    L.rectangle(city.bounds, {
      color: "#047857",
      weight: 1.5,
      dashArray: "5 4",
      fill: false,
      interactive: false
    }).addTo(cityLayer);
  });

  // ------------------------------------------------------------------ static time definitions
  var TIMES = [
    { id: "t0", label: "t0", note: "2015-09-10 18:00" },
    { id: "t1", label: "t1", note: "2015-09-11 06:00" },
    { id: "t2", label: "t2", note: "2015-09-11 18:00" },
    { id: "t3", label: "t3", note: "2015-09-12 06:00" },
    { id: "t4", label: "t4", note: "2015-09-12 18:00" },
    { id: "t5", label: "t5", note: "2015-09-13 06:00" },
    { id: "t6", label: "t6", note: "2015-09-13 18:00" },
    { id: "t7", label: "t7", note: "2015-09-16 10:20" }
  ];

  var activeTime  = "t0";
  var activeClick = null;
  var currentCity = null;
  var currentData = null;
  var dataCache   = {};
  var structCache = {};
  // Sequential loader lock — prevents concurrent script loads overwriting window.SCENARIO_V2_DATA
  var loadLock = Promise.resolve();

  // ------------------------------------------------------------------ time buttons
  function createTimeButtons() {
    var wrap = document.getElementById("time-buttons");
    TIMES.forEach(function (t) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "time-button";
      btn.textContent = t.label;
      btn.title = t.note;
      btn.dataset.timeId = t.id;
      btn.setAttribute("aria-pressed", t.id === activeTime ? "true" : "false");
      btn.addEventListener("click", function () { setTime(t.id); });
      wrap.appendChild(btn);
    });
  }

  function setTime(id) {
    activeTime = id;
    document.querySelectorAll(".time-button").forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.timeId === id ? "true" : "false");
    });
    if (currentData) {
      updateScenarioLayers();
      if (activeClick) routeFromClick(activeClick);
    }
  }

  // ------------------------------------------------------------------ city detection
  function detectCity(latlng) {
    var hits = [];
    manifest.forEach(function (city) {
      var s = city.bounds[0][0], w = city.bounds[0][1];
      var n = city.bounds[1][0], e = city.bounds[1][1];
      if (latlng.lat >= s && latlng.lat <= n && latlng.lng >= w && latlng.lng <= e) {
        var dy = latlng.lat - city.center[0];
        var dx = latlng.lng - city.center[1];
        hits.push({ city: city, d2: dy * dy + dx * dx });
      }
    });
    if (!hits.length) return null;
    hits.sort(function (a, b) { return a.d2 - b.d2; });
    return hits[0].city;
  }

  // ------------------------------------------------------------------ sequential data loader
  function loadCityData(code) {
    if (dataCache[code]) return Promise.resolve(dataCache[code]);
    var p = loadLock.then(function () {
      if (dataCache[code]) return dataCache[code];
      return new Promise(function (resolve, reject) {
        var script = document.createElement("script");
        script.src = "../scenario_cities/" + code + "/assets/data.js";
        script.onload = function () {
          var d = window.SCENARIO_V2_DATA;
          if (!d) { reject(new Error("no data")); return; }
          dataCache[code] = d;
          resolve(d);
        };
        script.onerror = function () { reject(new Error("load failed: " + code)); };
        document.head.appendChild(script);
      });
    });
    loadLock = p.catch(function () {});
    return p;
  }

  // ------------------------------------------------------------------ adjacency cache
  function getStructures(code, data) {
    if (structCache[code]) return structCache[code];
    var edgesById = new Map();
    var adjacency = new Map();
    data.graph.edges.forEach(function (edge) {
      edgesById.set(edge.id, edge);
      if (!adjacency.has(edge.u)) adjacency.set(edge.u, []);
      adjacency.get(edge.u).push(edge);
    });
    structCache[code] = { edgesById: edgesById, adjacency: adjacency };
    return structCache[code];
  }

  // ------------------------------------------------------------------ scenario layers
  function updateScenarioLayers() {
    if (!currentData || !currentCity) return;
    var data     = currentData;
    var st       = getStructures(currentCity.code, data);
    var closures = data.closures[activeTime] || [];

    floodLayer.clearLayers();
    if (data.floods[activeTime]) floodLayer.addData(data.floods[activeTime]);

    closedLayer.clearLayers();
    closures.forEach(function (eId) {
      var edge = st.edgesById.get(eId);
      if (!edge) return;
      L.polyline(edge.coords, { color: "#dc2626", weight: 3, opacity: 0.65 }).addTo(closedLayer);
    });

    var tObj = null;
    data.times.forEach(function (t) { if (t.id === activeTime) tObj = t; });
    document.getElementById("status-city").textContent     = currentCity.name;
    document.getElementById("status-progress").textContent = tObj ? tObj.progressPercent + "%" : "-";
    document.getElementById("status-closures").textContent = closures.length + " 本";
    document.getElementById("status-shelters").textContent = data.shelters.length + " 施設";
  }

  // ------------------------------------------------------------------ Dijkstra
  function MinHeap() { this.h = []; }
  MinHeap.prototype.push = function (item) {
    this.h.push(item);
    var i = this.h.length - 1;
    while (i > 0) {
      var p = (i - 1) >> 1;
      if (this.h[p].dist <= this.h[i].dist) break;
      var tmp = this.h[p]; this.h[p] = this.h[i]; this.h[i] = tmp;
      i = p;
    }
  };
  MinHeap.prototype.pop = function () {
    if (!this.h.length) return null;
    var top  = this.h[0];
    var last = this.h.pop();
    if (this.h.length) {
      this.h[0] = last;
      var i = 0, n = this.h.length;
      for (;;) {
        var l = i * 2 + 1, r = l + 1, s = i;
        if (l < n && this.h[l].dist < this.h[s].dist) s = l;
        if (r < n && this.h[r].dist < this.h[s].dist) s = r;
        if (s === i) break;
        var tmp2 = this.h[s]; this.h[s] = this.h[i]; this.h[i] = tmp2;
        i = s;
      }
    }
    return top;
  };

  function nearestNode(nodes, latlng) {
    var best = null, bestD = Infinity;
    Object.keys(nodes).forEach(function (id) {
      var c = nodes[id];
      var d = (c[0] - latlng.lat) * (c[0] - latlng.lat) + (c[1] - latlng.lng) * (c[1] - latlng.lng);
      if (d < bestD) { best = id; bestD = d; }
    });
    return best;
  }

  function dijkstra(startNode, shelterSet, closedSet, adjacency) {
    var dist = new Map([[startNode, 0]]);
    var prev = new Map();
    var heap = new MinHeap();
    heap.push({ node: startNode, dist: 0 });
    while (heap.h.length) {
      var cur = heap.pop();
      if (cur.dist !== dist.get(cur.node)) continue;
      if (shelterSet.has(cur.node)) return { node: cur.node, dist: cur.dist, prev: prev };
      (adjacency.get(cur.node) || []).forEach(function (edge) {
        if (closedSet.has(edge.id)) return;
        var nd = cur.dist + edge.length;
        var prev_d = dist.has(edge.v) ? dist.get(edge.v) : Infinity;
        if (nd < prev_d) {
          dist.set(edge.v, nd);
          prev.set(edge.v, { from: cur.node, edgeId: edge.id });
          heap.push({ node: edge.v, dist: nd });
        }
      });
    }
    return null;
  }

  function buildRoute(data, startNode, result, edgesById) {
    if (!result) return null;
    var ids = [], cur = result.node;
    while (cur !== startNode) {
      var step = result.prev.get(cur);
      if (!step) break;
      ids.push(step.edgeId);
      cur = step.from;
    }
    ids.reverse();
    var coords = [];
    ids.forEach(function (eId) {
      var edge = edgesById.get(eId);
      if (!edge) return;
      edge.coords.forEach(function (c) {
        var last = coords[coords.length - 1];
        if (!last || last[0] !== c[0] || last[1] !== c[1]) coords.push(c);
      });
    });
    var shelter = null;
    data.shelters.forEach(function (s) { if (s.node === result.node) shelter = s; });
    return { shelter: shelter, distance: result.dist, coords: coords };
  }

  // ------------------------------------------------------------------ click handler
  function routeFromClick(latlng) {
    activeClick = latlng;
    routeLayer.clearLayers();
    markerLayer.clearLayers();
    var resultEl = document.getElementById("route-result");

    var city = detectCity(latlng);
    if (!city) {
      resultEl.innerHTML =
        "<strong>対象外の地域です</strong><br>" +
        "茨城県内36市区町村の対応エリア（緑枠内）をクリックしてください。<br>" +
        "灰色のエリアはシミュレーション対象外です。";
      return;
    }

    L.marker(latlng).addTo(markerLayer);
    resultEl.textContent = city.name + " のデータを読み込み中...";

    loadCityData(city.code).then(function (data) {
      if (!currentData || currentCity.code !== city.code) {
        shelterLayer.clearLayers();
        currentCity = city;
        currentData = data;
        data.shelters.forEach(function (s) {
          L.circleMarker([s.lat, s.lon], {
            radius: 5, color: "#047857", fillColor: "#10b981", fillOpacity: 0.8, weight: 1
          }).bindPopup(s.name + "<br>収容人数: " + s.capacity).addTo(shelterLayer);
        });
        updateScenarioLayers();
      }

      var st        = getStructures(city.code, data);
      var startNode = nearestNode(data.graph.nodes, latlng);
      var closedSet = new Set(data.closures[activeTime] || []);
      var shelterSet = new Set(data.shelters.map(function (s) { return s.node; }));
      var result    = dijkstra(startNode, shelterSet, closedSet, st.adjacency);
      var route     = buildRoute(data, startNode, result, st.edgesById);

      if (!route || route.coords.length < 2) {
        resultEl.textContent = "この時刻では到達可能な避難所が見つかりません。";
        return;
      }

      L.polyline(route.coords, { color: "#111827", weight: 5, opacity: 0.82 }).addTo(routeLayer);
      var km = (route.distance / 1000).toFixed(2);
      resultEl.innerHTML =
        "<strong>" + route.shelter.name + "</strong><br>" +
        "都市: " + city.name + "<br>" +
        "距離: " + km + " km<br>" +
        "閉鎖道路を " + closedSet.size + " 本回避";

    }).catch(function () {
      resultEl.textContent = "データの読み込みに失敗しました。";
    });
  }

  // ------------------------------------------------------------------ legend
  var legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    var div = L.DomUtil.create("div", "legend");
    div.innerHTML =
      '<div class="legend-row"><span class="swatch swatch-flood"></span>浸水想定区域</div>' +
      '<div class="legend-row"><span class="swatch swatch-closed"></span>閉鎖道路</div>' +
      '<div class="legend-row"><span class="swatch swatch-route"></span>避難ルート</div>' +
      '<div class="legend-row"><span class="swatch swatch-area"></span>対応エリア（緑枠）</div>' +
      '<div class="legend-row"><span class="swatch swatch-outside"></span>対象外</div>';
    return div;
  };
  legend.addTo(map);

  // ------------------------------------------------------------------ init
  map.on("click", function (e) { routeFromClick(e.latlng); });
  createTimeButtons();
})();
"""
    (ASSETS_DIR / "app.js").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'app.js'}")


def write_style_css() -> None:
    content = """\
:root{color-scheme:light;--bg:#ffffff;--text:#1f2933;--muted:#6b7280;--line:#d9dee5;--surface:#f8fafc;--surface-hover:#eef2f7;--accent:#2563eb;--danger:#dc2626}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font-family:"Yu Gothic","Meiryo",system-ui,sans-serif}
.app-shell{display:grid;grid-template-columns:340px minmax(0,1fr);min-height:100vh}
.panel{border-right:1px solid var(--line);padding:28px 24px;background:var(--bg);overflow-y:auto}
.eyebrow{margin:0;color:var(--muted);font-size:13px}
h1{margin:4px 0 8px;font-size:24px;line-height:1.25}
.lead{margin:0 0 24px;color:var(--muted);font-size:14px;line-height:1.7}
.control-group{margin-top:24px}
h2{margin:0 0 10px;font-size:15px}
.time-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.time-button{min-height:42px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:inherit;cursor:pointer}
.time-button:hover,.time-button:focus-visible{border-color:var(--accent);background:var(--surface-hover);outline:none}
.time-button[aria-pressed="true"]{border-color:var(--accent);background:#eff6ff;color:#1d4ed8;font-weight:700}
.status-list{margin:0}
.status-list div{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}
dt{color:var(--muted);font-size:13px}
dd{margin:0;font-weight:700}
.result-box{min-height:112px;border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:12px;font-size:14px;line-height:1.6}
.result-box strong{display:block;margin-bottom:4px}
.back-link{display:inline-flex;margin-top:24px;color:var(--accent);font-size:14px;text-decoration:none}
.map-wrap,#map{min-height:100vh}
.legend{border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,0.95);padding:10px 12px;line-height:1.7;font-size:13px}
.legend-row{display:flex;align-items:center;gap:8px}
.swatch{width:18px;height:4px;border-radius:99px;display:inline-block}
.swatch-flood{height:12px;background:rgba(37,99,235,0.3);border:1px solid #1d4ed8}
.swatch-closed{background:var(--danger)}
.swatch-route{background:#111827}
.swatch-area{height:12px;background:transparent;border:2px dashed #047857}
.swatch-outside{height:12px;background:rgba(31,41,55,0.22);border:1px solid rgba(31,41,55,0.4)}
@media(max-width:860px){.app-shell{grid-template-columns:1fr}.panel{border-right:0;border-bottom:1px solid var(--line)}.map-wrap,#map{min-height:66vh}}
"""
    (ASSETS_DIR / "style.css").write_text(content, encoding="utf-8")
    print(f"[write] {ASSETS_DIR / 'style.css'}")


def write_html(n_cities: int) -> None:
    UNIFIED_DIR.mkdir(parents=True, exist_ok=True)
    html = f"""\
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>茨城県 統合避難ルートシミュレーション</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <link rel="stylesheet" href="assets/style.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" defer></script>
  <script src="assets/cities_manifest.js" defer></script>
  <script src="assets/app.js" defer></script>
</head>
<body>
  <main class="app-shell">
    <aside class="panel" aria-label="シミュレーション操作">
      <p class="eyebrow">茨城県 統合シミュレーション</p>
      <h1>避難ルート検索</h1>
      <p class="lead">
        茨城県内{n_cities}市区町村を対象とした統合シミュレーション。
        時刻を選び、地図上をクリックすると浸水回避ルートを検索します。
        灰色のエリアは対象外です。
      </p>
      <section class="control-group">
        <h2>時刻</h2>
        <div id="time-buttons" class="time-grid"></div>
      </section>
      <section class="control-group">
        <h2>状態</h2>
        <dl class="status-list">
          <div><dt>選択中の都市</dt><dd id="status-city">-</dd></div>
          <div><dt>浸水進行</dt><dd id="status-progress">-</dd></div>
          <div><dt>閉鎖道路</dt><dd id="status-closures">-</dd></div>
          <div><dt>避難所</dt><dd id="status-shelters">-</dd></div>
        </dl>
      </section>
      <section class="control-group">
        <h2>検索結果</h2>
        <div id="route-result" class="result-box">地図上をクリックして都市を選択してください。</div>
      </section>
      <a class="back-link" href="../index.html">&#8592; トップページへ戻る</a>
    </aside>
    <section class="map-wrap" aria-label="シミュレーション地図">
      <div id="map"></div>
    </section>
  </main>
</body>
</html>
"""
    (UNIFIED_DIR / "scenario_route_simulation.html").write_text(html, encoding="utf-8")
    print(f"[write] {UNIFIED_DIR / 'scenario_route_simulation.html'}")


def main() -> None:
    cities = []
    for code in sorted(_CITY_NAMES):
        info = extract_city_info(code)
        if info:
            cities.append(info)
        else:
            print(f"[skip] {code} ({_CITY_NAMES[code]}) — data.js not found")

    print(f"\n{len(cities)} 都市を検出")
    write_cities_manifest(cities)
    write_app_js()
    write_style_css()
    write_html(len(cities))
    print(f"\n完了: output/unified/ に統合ページを生成しました")


if __name__ == "__main__":
    main()
