#!/usr/bin/env python3
# WHO FluNet 한국 주간 데이터(2016~) — 절기별 양성률 곡선용
import datetime
import urllib.request, urllib.parse, json, ssl
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
q={"$filter":"COUNTRY_CODE eq 'KOR' and ISO_YEAR ge 2016",
   "$select":"ISO_YEAR,ISO_WEEK,SPEC_PROCESSED_NB,INF_A,INF_B,AH3,AH1N12009,BVIC_NODEL,BVIC_2DEL,BVIC_3DEL,BVIC_DELUNK,BYAM",
   "$orderby":"ISO_YEAR,ISO_WEEK","$top":"2000"}
url="https://xmart-api-public.who.int/FLUMART/VIW_FNT?"+urllib.parse.urlencode(q)
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
v=json.load(urllib.request.urlopen(req,timeout=90,context=ctx)).get("value",[])
rows=[]
for r in v:
    spec=r.get("SPEC_PROCESSED_NB") or 0
    a=r.get("INF_A") or 0; b=r.get("INF_B") or 0
    rows.append({"y":r["ISO_YEAR"],"w":r["ISO_WEEK"],"spec":spec,"a":a,"b":b,
                 "pos":round(100*(a+b)/spec,2) if spec else None})
json.dump({"as_of":datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"),"korea_weekly":rows,"source":"WHO FluNet KOR weekly"},
          open("06_인플루엔자_감시_대시보드/data_kor_weekly.json","w"),ensure_ascii=False)
print("weeks:",len(rows),"| span:",rows[0]["y"],"-",rows[-1]["y"])
