import urllib.request, re, html, ssl, time, csv
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
BASE="https://dportal.kdca.go.kr/pot/bbs/BD_selectBbsList.do?q_bbsSn=1001&q_currPage="
VIEW="https://dportal.kdca.go.kr/pot/bbs/BD_selectBbs.do"

row_re=re.compile(
  r'<td\s+class="num">\s*(\d+)\s*</td>.*?'
  r'<a href="(/pot/bbs/BD_selectBbs\.do\?[^"]+)">(.*?)</a>.*?'
  r'<td>(\d{4}\.\d{2}\.\d{2})</td>\s*<td>(\d+)</td>',
  re.S)

rows=[]
for pg in range(1,41):
    url=BASE+str(pg)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        t=urllib.request.urlopen(req,timeout=40,context=ctx).read().decode('utf-8','ignore')
    except Exception as e:
        print("ERR pg",pg,e); continue
    found=row_re.findall(t)
    for num,href,title,date,views in found:
        title=html.unescape(re.sub(r'<[^>]+>','',title)).strip()
        doc=re.search(r'q_bbsDocNo=([^&]+)',href)
        rows.append({'num':int(num),'title':title,'date':date,'views':int(views),
                     'doc':doc.group(1) if doc else '','url':'https://dportal.kdca.go.kr'+html.unescape(href)})
    print(f"page {pg}: {len(found)} rows (total {len(rows)})")
    time.sleep(0.25)

# dedupe by doc
seen={}
for r in rows: seen[r['doc'] or r['title']]=r
rows=sorted(seen.values(), key=lambda r:-r['num'])
out='02_지침_정리/data/지침_전체목록_감염병포털.csv'
import os; os.makedirs('02_지침_정리/data',exist_ok=True)
with open(out,'w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(['번호','제목','등록일','조회','문서번호','URL'])
    for r in rows: w.writerow([r['num'],r['title'],r['date'],r['views'],r['doc'],r['url']])
print("SAVED",len(rows),"->",out)
