#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""질병관리청 지침 목록 품질검수 — 용어 비일관·표기 이상·오탈자 후보 탐지.
입력: data/지침_전체목록_감염병포털.csv  (crawl_guides.py 산출)
출력: 표준출력 리포트 + data/검수_후보.csv
주의: 자동 '후보' 제시까지만. 최종 판정은 사람이 한다. 원문 표기는 임의 수정 금지.
"""
import csv, re, os, sys
from collections import defaultdict

SRC='02_지침_정리/data/지침_전체목록_감염병포털.csv'
if not os.path.exists(SRC): SRC=os.path.join(os.path.dirname(__file__),'data/지침_전체목록_감염병포털.csv')

rows=list(csv.DictReader(open(SRC,encoding='utf-8-sig')))
titles=[(r['번호'],r['제목']) for r in rows]
findings=[]  # (유형, 번호, 원문, 근거/제안)

# 1) 용어 비일관 — 같은 개념의 다른 표기 공존 탐지
variant_groups={
 '코로나19 표기':[r'코로나바이러스감염증-?19', r'코로나19', r'COVID-?19', r'코로나-19'],
 '엠폭스/원숭이두창':[r'엠폭스', r'원숭이두창', r'MPOX', r'monkeypox'],
 '전염병/감염병':[r'전염병', r'감염병'],
 '군/급 체계':[r'제\s*[1-5]\s*군감염병', r'제\s*[1-4]\s*급감염병'],
 'AIDS 표기':[r'후천성면역결핍증', r'에이즈', r'AIDS', r'HIV/AIDS'],
 '결핵 진단/진료':[r'진료지침', r'진단지침'],
}
for label,pats in variant_groups.items():
    hits=defaultdict(list)
    for num,tt in titles:
        for p in pats:
            if re.search(p,tt,re.I): hits[p].append(num)
    used=[p for p in pats if hits[p]]
    if len(used)>1:
        findings.append(('용어혼용', '-', label,
            ' / '.join(f'"{p}"({len(hits[p])}건)' for p in used)))

# 2) 표기 이상 — 공백/괄호/판 표기
for num,tt in titles:
    if re.search(r'\s{2,}',tt): findings.append(('이중공백',num,tt,'연속 공백'))
    if tt.count('(')!=tt.count(')'): findings.append(('괄호불일치',num,tt,'괄호 짝 안 맞음'))
    if re.search(r'제\s*\d+\s*판.*제\s*\d+\s*판',tt): findings.append(('판표기중복',num,tt,'판 표기 2회'))
    # 흔한 오타 후보
    for bad,good in [('관리지치','관리지침'),('지침침','지침'),('감염명','감염병'),
                     ('예발접종','예방접종'),('바이러스스','바이러스'),('겸염병','감염병')]:
        if bad in tt: findings.append(('오타후보',num,tt,f'{bad}→{good}'))
    # 법정 병명 정규화 — 정식 명칭 오기 탐지
    if '중증열성혈소판' in tt and '감소' not in tt:
        findings.append(('병명오기',num,tt,'중증열성혈소판증후군→중증열성혈소판감소증후군(SFTS)'))
    if '유행성이하선염' in tt.replace('유행성이하선염','') : pass
    for bad,good in [('쭈쭈가무시','쯔쯔가무시'),('츠츠가무시','쯔쯔가무시'),
                     ('부르셀라','브루셀라'),('뎅기','뎅기'),('디프테리아','디프테리아')]:
        if bad in tt and bad!=good: findings.append(('병명오기',num,tt,f'{bad}→{good}'))
    # 연도 표기 이상(미래 과다/형식)
    m=re.search(r'(19|20)\d{2}',tt)

# 3) 연도/판 누락 등 메타 점검
noyear=[num for num,tt in titles if not re.search(r'(20\d{2}|제\s*\d+\s*판|절기)',tt)]

# ---- 리포트 출력 ----
print(f"# 지침 목록 품질검수 리포트")
print(f"- 대상: {len(rows)}건 (출처 감염병포털 q_bbsSn=1001)\n")
print(f"## 1. 용어 혼용/표기 이상/오타 후보: {len(findings)}건")
for typ,num,src,note in findings:
    print(f"- [{typ}] (#{num}) {src[:40]} → {note}")
print(f"\n## 2. 연도·판 표기 없는 제목: {len(noyear)}건")
print("  " + (", ".join(f"#{n}" for n in noyear[:30]) or "없음"))

os.makedirs('02_지침_정리/data',exist_ok=True)
with open('02_지침_정리/data/검수_후보.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(['유형','번호','원문/대상','근거·제안'])
    for row in findings: w.writerow(row)
print(f"\n저장: 02_지침_정리/data/검수_후보.csv ({len(findings)}건)")
