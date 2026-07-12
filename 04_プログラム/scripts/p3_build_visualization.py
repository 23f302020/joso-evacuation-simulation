"""Build the Phase 3 null-result visualization and traffic animation."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


PROGRAM = Path(__file__).resolve().parent.parent
REGION = PROGRAM / "output" / "sumo" / "regions" / "08211"
FCD = REGION / "results" / "archive_runs" / "20260712T101241222770_scenario_b_final" / "scenario_b_fcd.xml"
OUTPUT = PROGRAM / "output" / "sumo" / "viz" / "phase3_viz.html"


def selected(vehicle_id: str) -> bool:
    return vehicle_id.startswith("bus_") or sum(vehicle_id.encode("utf-8")) % 23 == 0


def load_frames() -> dict[str, list[list[float]]]:
    frames: dict[str, list[list[float]]] = {}
    current = 0
    for event, elem in ET.iterparse(FCD, events=("start", "end")):
        if event == "start" and elem.tag == "timestep":
            current = int(float(elem.attrib["time"]))
        elif event == "end" and elem.tag == "vehicle":
            vehicle_id = elem.attrib.get("id", "")
            if selected(vehicle_id):
                frames.setdefault(vehicle_id, []).append(
                    [current, float(elem.attrib["x"]), float(elem.attrib["y"])]
                )
            elem.clear()
    return frames


def main() -> None:
    frames = load_frames()
    payload = json.dumps(frames, separators=(",", ":"))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Phase 3 結果可視化</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;background:#f5f7f8;color:#172126}}header{{padding:22px 5vw;background:#fff;border-bottom:1px solid #d8e0e3}}h1{{margin:0;font-size:24px;letter-spacing:0}}main{{max-width:1180px;margin:auto;padding:24px 5vw 48px}}section{{margin:0 0 30px}}h2{{font-size:18px;margin:0 0 12px}}.plots{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.plot{{background:#fff;border:1px solid #d8e0e3;border-radius:6px;padding:18px;min-height:240px}}.axis{{position:relative;height:125px;margin:35px 18px 0;border-bottom:2px solid #526067}}.zero{{position:absolute;left:13.9%;top:0;bottom:0;border-left:2px dashed #b52424}}.band{{position:absolute;height:18px;background:#16827a;top:24px;border-radius:3px}}.band.cons{{top:64px;background:#4574a8}}.dot{{position:absolute;width:13px;height:13px;border-radius:50%;background:#16827a;transform:translate(-50%,-50%)}}.label{{font-size:12px;color:#526067}}.legend{{display:flex;gap:16px;font-size:12px;margin-top:12px}}.sw{{width:12px;height:12px;display:inline-block;margin-right:5px}}.traffic{{background:#111b20;border-radius:6px;overflow:hidden}}canvas{{width:100%;height:520px;display:block}}.controls{{display:flex;align-items:center;gap:12px;padding:12px;background:#fff;border:1px solid #d8e0e3;border-top:0}}input[type=range]{{flex:1}}button{{border:0;background:#176d66;color:#fff;padding:9px 14px;border-radius:4px}}@media(max-width:760px){{.plots{{grid-template-columns:1fr}}canvas{{height:420px}}}}
</style></head><body><header><h1>Phase 3 デマンド交通バス比較</h1></header><main>
<section><h2>A/B完了率差の不確実性帯</h2><div class="plots"><div class="plot"><div class="label">差（B−A、%pt）: 赤破線が0</div><div class="axis"><div class="zero"></div><div class="band" style="left:8.0%;width:74.7%"></div><div class="band cons" style="left:8.0%;width:70.9%"></div></div><div class="legend"><span><i class="sw" style="background:#16827a"></i>raw −4.23〜+22.67</span><span><i class="sw" style="background:#4574a8"></i>保守 −4.23〜+21.32</span></div></div>
<div class="plot"><div class="label">A側完了率（%）: seed別</div><div class="axis" id="bimodal"><span class="dot" style="left:5%;top:74%"></span><span class="dot" style="left:88%;top:42%"></span><span class="dot" style="left:93%;top:24%"></span></div><div class="legend">75.02% / 95.44% / 96.58% — 早期広域ロックと高完了regime</div></div></div></section>
<section><h2>基準5台シナリオの交通アニメーション</h2><div class="traffic"><canvas id="map"></canvas></div><div class="controls"><button id="play">再生</button><input id="time" type="range" min="0" max="21600" step="60" value="0"><output id="clock">00:00</output></div><div class="legend"><span><i class="sw" style="background:#f1c84b"></i>バス</span><span><i class="sw" style="background:#64b5f6"></i>車両（決定論的サンプル）</span></div></section>
</main><script>const data={payload};const canvas=document.getElementById('map'),ctx=canvas.getContext('2d'),slider=document.getElementById('time'),clock=document.getElementById('clock'),play=document.getElementById('play');let timer=null;const all=Object.values(data).flat();const xs=all.map(x=>x[1]),ys=all.map(x=>x[2]),bounds=[Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)];function resize(){{canvas.width=canvas.clientWidth*devicePixelRatio;canvas.height=canvas.clientHeight*devicePixelRatio;draw()}}function frameAt(a,t){{let z=null;for(const f of a){{if(f[0]>t)break;z=f}}return z}}function draw(){{const t=+slider.value,w=canvas.width,h=canvas.height;ctx.fillStyle='#111b20';ctx.fillRect(0,0,w,h);ctx.globalAlpha=.18;ctx.strokeStyle='#64808c';for(let i=1;i<8;i++){{ctx.beginPath();ctx.moveTo(i*w/8,0);ctx.lineTo(i*w/8,h);ctx.stroke();ctx.beginPath();ctx.moveTo(0,i*h/8);ctx.lineTo(w,i*h/8);ctx.stroke()}}ctx.globalAlpha=1;for(const [id,a] of Object.entries(data)){{const f=frameAt(a,t);if(!f)continue;const x=(f[1]-bounds[0])/(bounds[1]-bounds[0])*w,y=h-(f[2]-bounds[2])/(bounds[3]-bounds[2])*h;ctx.fillStyle=id.startsWith('bus_')?'#f1c84b':'#64b5f6';ctx.beginPath();ctx.arc(x,y,id.startsWith('bus_')?5:2.2,0,Math.PI*2);ctx.fill()}}clock.value=String(Math.floor(t/3600)).padStart(2,'0')+':'+String(Math.floor(t%3600/60)).padStart(2,'0')}}slider.oninput=draw;play.onclick=()=>{{if(timer){{clearInterval(timer);timer=null;play.textContent='再生'}}else{{play.textContent='停止';timer=setInterval(()=>{{slider.value=(+slider.value+60)%21660;draw()}},100)}}}};addEventListener('resize',resize);resize();</script></body></html>"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"[INFO] saved: {OUTPUT} ({len(frames)} sampled vehicles)")


if __name__ == "__main__":
    main()
