from pathlib import Path
import hashlib,json,urllib.request,datetime
base=Path(__file__).resolve().parent
sources=[('city_verification','https://www.city.joso.lg.jp/data/doc/1674176111_doc_6_0.pdf'),('cabinet_rescue_stockyard','https://www.bousai.go.jp/kaigirep/kentokai/hinanzyokakuho/wg_situ/pdf/dai5kaisiryo1.pdf'),('cabinet_disaster_overview','https://www.bousai.go.jp/fusuigai/suigaiworking/pdf/dai1kai/siryo1.pdf')]
records=[]
for key,url in sources:
    target=base/(key+'.pdf')
    if target.exists(): raise RuntimeError('Do not overwrite '+str(target))
    with urllib.request.urlopen(url,timeout=60) as r:
        body=r.read()
        if not body.startswith(b'%PDF'): raise RuntimeError('Not PDF '+url)
        record=dict(id=key,requested_url=url,final_url=r.url,status=r.status,content_type=r.headers.get('Content-Type'),last_modified=r.headers.get('Last-Modified'),retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
    target.write_bytes(body)
    records.append(record)
(base/'source_metadata.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(records,ensure_ascii=False,indent=2))
