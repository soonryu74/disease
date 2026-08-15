#!/usr/bin/env python3
# WHO FluNet(RespiMart) 연도별 전세계 + 한국 아형 집계 수집
import urllib.request, urllib.parse, json, ssl, time
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
BASE="https://xmart-api-public.who.int/FLUMART/VIW_FNT"
COLS=["AH1","AH3","AH1N12009","AH5","ANOTSUBTYPED","ANOTSUBTYPABLE","INF_A",
      "BYAM","BVIC_NODEL","BVIC_2DEL","BVIC_3DEL","BVIC_DELUNK","BNOTDETERMINED","INF_B","INF_ALL"]
def fetch_year(y, country=None):
    filt=f"ISO_YEAR eq {y}"
    if country: filt+=f" and COUNTRY_CODE eq '{country}'"
    q={"$filter":filt,"$select":",".join(COLS),"$top":"60000"}
    url=BASE+"?"+urllib.parse.urlencode(q)
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    v=json.load(urllib.request.urlopen(req,timeout=90,context=ctx)).get("value",[])
    s=lambda k: sum((r.get(k) or 0) for r in v)
    bvic=s("BVIC_NODEL")+s("BVIC_2DEL")+s("BVIC_3DEL")+s("BVIC_DELUNK")
    return {"year":y,"rows":len(v),
            "AH1":s("AH1"),"AH3":s("AH3"),"H1N1pdm":s("AH1N12009"),"AH5":s("AH5"),
            "A_nosub":s("ANOTSUBTYPED")+s("ANOTSUBTYPABLE"),"INF_A":s("INF_A"),
            "BVic":bvic,"BYam":s("BYAM"),"B_nodet":s("BNOTDETERMINED"),"INF_B":s("INF_B")}
world=[]; korea=[]
for y in range(1997,2027):
    try:
        world.append(fetch_year(y)); print("W",y,world[-1]["INF_A"],world[-1]["INF_B"])
    except Exception as e: print("W ERR",y,e)
    try:
        korea.append(fetch_year(y,"KOR")); print("  K",y,korea[-1]["INF_A"],korea[-1]["INF_B"])
    except Exception as e: print("K ERR",y,e)
    time.sleep(0.2)
json.dump({"world":world,"korea":korea,"source":"WHO FluNet (xmart VIW_FNT)","note":"연도별 전세계/한국 검출건 합계"},
          open("06_인플루엔자_감시_대시보드/data_flunet.json","w"),ensure_ascii=False,indent=1)
print("SAVED", len(world),"years")
