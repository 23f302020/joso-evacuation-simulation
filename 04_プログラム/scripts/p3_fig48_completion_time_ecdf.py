#!/usr/bin/env python3
"""図4-8-1 Type3/4(救出走行)避難完了時間ECDF 8run重ね描き（依存ゼロ・SVG出力）。
真実源=phase3r_e1_replicate_metrics.csv（run→artifact_dir・完了率）。決定108準拠・非方向設計。"""
import csv, os, sys

BASE = "/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究"
EVAL = os.path.join(BASE, "04_プログラム/output/sumo/regions/08211/evaluation")
RESULTS = os.path.join(BASE, "04_プログラム/output/sumo/regions/08211/results")
OUT = os.path.join(BASE, "06_研究結果/phase3/figures/fig4-8-1_completion_time_ecdf.svg")

def wsl_path(win_dir):
    tail = win_dir.replace("\\", "/").split("/results/")[-1]  # archive_runs/<dir>
    return os.path.join(RESULTS, tail)

# --- run定義を真実源CSVから読む ---
runs = []
with open(os.path.join(EVAL, "phase3r_e1_replicate_metrics.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        scen = r["scenario"]  # A / B
        vlog = f"scenario_{scen.lower()}_vehicle_log.csv"
        runs.append({
            "run": r["run"], "seed": r["seed"], "scen": scen,
            "rate": float(r["raw_completion_rate"]) * 100.0,
            "vlog": os.path.join(wsl_path(r["artifact_dir"]), vlog),
        })

# --- 各runの rescue_origin_* かつ arrived の duration を収集 ---
for rr in runs:
    durs = []
    with open(rr["vlog"], encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["vehicle_id"].startswith("rescue_origin_") and row["arrived"] == "True":
                durs.append(int(row["duration"]))
    durs.sort()
    rr["durs"] = durs
    rr["n"] = len(durs)
    rr["median"] = durs[len(durs)//2] if durs else 0

xmax = max(d for rr in runs for d in rr["durs"])
xmax = ((xmax // 300) + 1) * 300  # 5分刻みで切り上げ

# --- 検証用サマリ（stderr） ---
for rr in runs:
    print(f'{rr["run"]:5} seed={rr["seed"]:>5} n={rr["n"]:5} median={rr["median"]:5}s rate={rr["rate"]:.2f}%', file=sys.stderr)
print(f"xmax={xmax}s", file=sys.stderr)

# --- SVG座標系 ---
W, H = 960, 640
ML, MR, MT, MB = 78, 250, 64, 132  # 右に凡例余白
PW, PH = W - ML - MR, H - MT - MB
def X(t): return ML + PW * (t / xmax)
def Y(p): return MT + PH * (1 - p)

# 色: A=ティール系, A#2=アンバー強調(非方向の注意色), B=ブルー系。赤緑の良悪配色は使わない
COL = {
    "A#1": ("#0f6d66", "solid"), "A#2": ("#d98a1f", "dashed"), "A#3": ("#3aa89f", "solid"),
    "B#1": ("#2f4f7a", "solid"), "B#2": ("#4574a8", "solid"), "B#3": ("#5a8fc4", "solid"),
    "B#4": ("#7aa9d6", "solid"), "B#5": ("#9cc2e4", "solid"),
}

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="\'Yu Gothic\',\'Meiryo\',\'Noto Sans CJK JP\',sans-serif">')
svg.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
# タイトル
svg.append(f'<text x="{ML}" y="30" font-size="17" font-weight="bold" fill="#111b20">図4-8-1 交通弱者(Type3/4・救出走行)避難完了時間のECDF（8run重ね描き）</text>')
svg.append(f'<text x="{ML}" y="50" font-size="12" fill="#526067">A側3run（自家用車のみ）・B側5run（バス追加）。到着車のみの条件付き分布。方向主張はしない（決定108）。</text>')
# 目盛グリッド（Y: 0,0.25,0.5,0.75,1.0）
for p in (0, .25, .5, .75, 1.0):
    y = Y(p)
    svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML+PW}" y2="{y:.1f}" stroke="#e3e9ec" stroke-width="1"/>')
    svg.append(f'<text x="{ML-10}" y="{y+4:.1f}" font-size="11" fill="#526067" text-anchor="end">{p:.2f}</text>')
# X目盛（15分=900s刻み・印刷可読性のため疎に。方向性には無影響）
t = 0
while t <= xmax:
    x = X(t)
    svg.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+PH}" stroke="#f1f4f6" stroke-width="1"/>')
    svg.append(f'<text x="{x:.1f}" y="{MT+PH+18}" font-size="11" fill="#526067" text-anchor="middle">{t//60}</text>')
    t += 900
# 軸
svg.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+PH}" stroke="#526067" stroke-width="1.5"/>')
svg.append(f'<line x1="{ML}" y1="{MT+PH}" x2="{ML+PW}" y2="{MT+PH}" stroke="#526067" stroke-width="1.5"/>')
svg.append(f'<text x="{ML+PW/2}" y="{MT+PH+42}" font-size="12.5" fill="#111b20" text-anchor="middle">避難完了時間（出発→到着の所要・分）</text>')
svg.append(f'<text x="20" y="{MT+PH/2}" font-size="12.5" fill="#111b20" text-anchor="middle" transform="rotate(-90 20 {MT+PH/2:.0f})">累積割合（到着車ベース）</text>')

# ECDFステップ線
def ecdf_path(durs):
    n = len(durs)
    pts = [f'M {X(0):.1f} {Y(0):.1f}']
    prev_p = 0.0
    for i, d in enumerate(durs):
        p = (i + 1) / n
        x = X(d)
        pts.append(f'L {x:.1f} {Y(prev_p):.1f}')  # 水平
        pts.append(f'L {x:.1f} {Y(p):.1f}')        # 垂直
        prev_p = p
    return " ".join(pts)

for rr in runs:
    col, style = COL[rr["run"]]
    dash = ' stroke-dasharray="7 4"' if style == "dashed" else ""
    w = 2.4 if rr["run"] == "A#2" else 1.8
    svg.append(f'<path d="{ecdf_path(rr["durs"])}" fill="none" stroke="{col}" stroke-width="{w}"{dash} opacity="0.92"/>')

# A#2注記
a2 = next(r for r in runs if r["run"] == "A#2")
ax = X(a2["median"]); ay = Y(0.5)
svg.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="3.5" fill="#d98a1f"/>')
svg.append(f'<text x="{ax+8:.1f}" y="{ay-6:.1f}" font-size="11" fill="#a5670f">A#2(seed42)=完了率75.87%のロックregime</text>')
svg.append(f'<text x="{ax+8:.1f}" y="{ay+8:.1f}" font-size="11" fill="#a5670f">（母集団非可換・生存者バイアス）</text>')

# 凡例
lx = ML + PW + 22
ly = MT + 6
svg.append(f'<text x="{lx}" y="{ly}" font-size="12" font-weight="bold" fill="#111b20">run（seed・完了率・到着n）</text>')
ly += 20
for rr in runs:
    col, style = COL[rr["run"]]
    dash = ' stroke-dasharray="6 3"' if style == "dashed" else ""
    svg.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+26}" y2="{ly-4}" stroke="{col}" stroke-width="2.6"{dash}/>')
    svg.append(f'<text x="{lx+34}" y="{ly}" font-size="11" fill="#233">{rr["run"]}  seed{rr["seed"]}  {rr["rate"]:.1f}%  n={rr["n"]}</text>')
    ly += 21

# キャプション（非方向・スコープ注記）
cap = [
    "注記：本図は到着した救出走行車のみの条件付き完了時間分布であり、生存者バイアスを含む。A#2は非到着が多くregimeロック",
    "のため他runと母集団が非可換。曲線の左右差を「バスで速い/遅い」と読む方向主張はしない（決定105/108）。完了率と対で解釈",
    "すること。バス乗客（B側のみ・n\'中央値125）は完了時間分布に含めず、需要充足率（§4.6.2）として別に報告する。",
]
cy = MT + PH + 58
for line in cap:
    svg.append(f'<text x="{ML}" y="{cy}" font-size="10.5" fill="#64808c">{esc(line)}</text>')
    cy += 16
svg.append('</svg>')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print("WROTE", OUT, f"({os.path.getsize(OUT)} bytes)", file=sys.stderr)
