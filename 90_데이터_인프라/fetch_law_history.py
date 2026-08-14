import urllib.request, urllib.parse, xml.etree.ElementTree as ET, ssl, time, csv, os

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OC = os.environ.get('LAW_OC', 'test')  # export LAW_OC=본인OC 하면 자동 사용

def fetch(query):
    rows=[]
    for page in range(1,10):
        params=urllib.parse.urlencode({'OC':OC,'target':'eflaw','query':query,
            'type':'XML','display':'100','page':str(page)})
        url='https://www.law.go.kr/DRF/lawSearch.do?'+params
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            root=ET.fromstring(urllib.request.urlopen(req,timeout=30,context=ctx).read())
        except Exception as e: print("ERR",e); break
        laws=root.findall('law')
        if not laws: break
        for l in laws:
            g=lambda t:(l.find(t).text if l.find(t) is not None else '')
            rows.append([g('법령구분명'),g('법령명한글'),g('법령ID'),g('법령일련번호'),
                g('제개정구분명'),g('공포일자'),g('공포번호'),g('시행일자'),g('현행연혁코드')])
        time.sleep(0.25)
    return rows

allrows=[]
for q in ['감염병의 예방 및 관리에 관한 법률','전염병예방법']:
    allrows+=fetch(q)

names={'감염병의 예방 및 관리에 관한 법률','전염병예방법',
       '감염병의 예방 및 관리에 관한 법률 시행령','전염병예방법시행령',
       '감염병의 예방 및 관리에 관한 법률 시행규칙','전염병예방법시행규칙'}
rows=[r for r in allrows if r[1] in names]
seen={}
for r in rows: seen[r[3]]=r  # dedupe by 법령일련번호
rows=sorted(seen.values(), key=lambda r:(r[0],r[7]))

out='/home/user/disease/01_감염병예방법_연혁/data/감염병예방법_연혁_전체.csv'
with open(out,'w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f)
    w.writerow(['법령구분','법령명','법령ID','법령일련번호(MST)','제개정구분','공포일자','공포번호','시행일자','연혁코드'])
    w.writerows(rows)
print("saved",len(rows),"rows ->",out)
from collections import Counter
print("구분별:",Counter(r[0] for r in rows))
