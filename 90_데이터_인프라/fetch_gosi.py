#!/usr/bin/env python3
# 질병관리청 감염병 지정 고시 연혁 수집 (법제처 target=admrul)
# 토론 9위: 고시번호·발령일자 = '처벌과 권리의 시적 경계'
import urllib.request, urllib.parse, json, ssl, datetime, os
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OC=os.environ.get('LAW_OC','test')
def search(query, nw=2):
    q={'OC':OC,'target':'admrul','query':query,'type':'JSON','display':'100','nw':str(nw)}
    url='https://www.law.go.kr/DRF/lawSearch.do?'+urllib.parse.urlencode(q)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(req,timeout=40,context=ctx))
rows=[]
for nw in (1,2):  # 1=현행, 2=연혁 (미지원 시 무시)
    try:
        d=search('질병관리청장이 지정하는 감염병', nw)
        sec=d.get('AdmRulSearch',{})
        items=sec.get('admrul',[])
        if isinstance(items,dict): items=[items]
        for it in items:
            rows.append(dict(name=it.get('행정규칙명'),kind=it.get('행정규칙종류'),
                date=it.get('발령일자'),no=it.get('발령번호'),status=it.get('현행연혁구분'),
                sn=it.get('행정규칙일련번호')))
    except Exception as e: print('ERR nw',nw,e)
seen={}; [seen.setdefault(r['sn'],r) for r in rows]
rows=sorted(seen.values(), key=lambda r:r['date'] or '')
out=dict(as_of=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'),
         source='법제처 Open API target=admrul (OC='+OC+')',
         note='발령일자·발령번호가 급수 지정·조정의 법적 시점. 시행일은 고시 본문 확인 필요.',
         gosi=rows)
json.dump(out,open('01_감염병예방법_연혁/data/감염병지정고시_연혁.json','w'),ensure_ascii=False,indent=1)
print('saved',len(rows),'gosi versions')
for r in rows: print(' ',r['date'],r['no'],r['status'],r['name'][:30])
