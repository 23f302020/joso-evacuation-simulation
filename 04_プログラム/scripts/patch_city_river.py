"""既存の市区町村別シナリオページに鬼怒川レイヤーを追加するパッチスクリプト。

変更対象（各都市ディレクトリ）:
  scenario_route_simulation.html  → kinugawa_river.js の <script> タグを追加
  assets/app.js                  → 鬼怒川レイヤーコードを追加、凡例更新
  assets/style.css               → .swatch-river CSS を追加

使い方:
    python patch_city_river.py
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
OUTPUT_DIR  = SCRIPT_DIR.parent / "output"
CITIES_DIR  = OUTPUT_DIR / "scenario_cities"

# ----- 挿入するコード定数 -----

_KINUGAWA_SCRIPT_TAG = '<script src="../kinugawa_river.js" defer></script>'
_APPJS_ANCHOR        = '<script src="assets/app.js" defer></script>'

_KINUGAWA_LAYER_JS = """\

  // ------------------------------------------------------------------ Kinugawa River layer
  if (window.KINUGAWA_RIVER) {
    L.geoJSON(window.KINUGAWA_RIVER, {
      style: function (f) {
        var t = f.geometry ? f.geometry.type : "";
        if (t === "Polygon" || t === "MultiPolygon") {
          return { color: "#0d9488", weight: 1.5, opacity: 0.85, fillColor: "#0d9488", fillOpacity: 0.30 };
        }
        return { color: "#0d9488", weight: 3.5, opacity: 0.85, fill: false };
      }
    }).bindTooltip("鬼怒川", { sticky: true, direction: "top" }).addTo(map);
  }"""

_KINUGAWA_LEGEND_ENTRY = (
    '<div class="legend-row"><span class="swatch swatch-river"></span>鬼怒川</div>'
)
_LEGEND_ANCHOR  = '<div class="legend-row"><span class="swatch swatch-flood"></span>'
_RIVER_CSS      = ".swatch-river{background:#0d9488}\n"
_CSS_ANCHOR     = ".swatch-flood{"


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if _KINUGAWA_SCRIPT_TAG in text:
        return False  # already patched
    text = text.replace(
        _APPJS_ANCHOR,
        _KINUGAWA_SCRIPT_TAG + "\n  " + _APPJS_ANCHOR,
    )
    path.write_text(text, encoding="utf-8")
    return True


def patch_appjs(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    # 凡例に鬼怒川エントリを追加
    if _LEGEND_ANCHOR in text and _KINUGAWA_LEGEND_ENTRY not in text:
        text = text.replace(
            _LEGEND_ANCHOR,
            _KINUGAWA_LEGEND_ENTRY + "\n      " + _LEGEND_ANCHOR,
        )
        changed = True

    # IIFE 末尾に鬼怒川レイヤーコードを追加
    if _KINUGAWA_LAYER_JS not in text:
        tail = "})();"
        stripped = text.rstrip()
        if stripped.endswith(tail):
            text = stripped[:-len(tail)] + _KINUGAWA_LAYER_JS + "\n" + tail + "\n"
        else:
            text = stripped + "\n" + _KINUGAWA_LAYER_JS + "\n"
        changed = True

    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def patch_css(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if _RIVER_CSS.strip() in text:
        return False
    text = text.replace(_CSS_ANCHOR, _RIVER_CSS + _CSS_ANCHOR)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    city_dirs = sorted(d for d in CITIES_DIR.iterdir() if d.is_dir() and d.name.isdigit())
    if not city_dirs:
        print(f"[ERROR] 市区町村ディレクトリが見つかりません: {CITIES_DIR}")
        return

    patched_html = patched_app = patched_css = 0

    for city_dir in city_dirs:
        code = city_dir.name
        html_path  = city_dir / "scenario_route_simulation.html"
        appjs_path = city_dir / "assets" / "app.js"
        css_path   = city_dir / "assets" / "style.css"

        if not html_path.exists():
            print(f"[skip] {code}: HTML 未生成")
            continue

        if patch_html(html_path):
            patched_html += 1
        if appjs_path.exists() and patch_appjs(appjs_path):
            patched_app += 1
        if css_path.exists() and patch_css(css_path):
            patched_css += 1

    print(f"\n=== パッチ完了 ({len(city_dirs)} 市区町村) ===")
    print(f"  HTML   更新: {patched_html} / スキップ: {len(city_dirs) - patched_html}")
    print(f"  app.js 更新: {patched_app}")
    print(f"  CSS    更新: {patched_css}")


if __name__ == "__main__":
    main()
