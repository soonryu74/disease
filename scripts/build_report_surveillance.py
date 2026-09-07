#!/usr/bin/env python3
"""PHWR 환자감시(신고) 파싱 결과 → 12_신고_감시/data/*.csv

전수감시는 호마다 **금주 1주치**만 실린다(병원체감시는 4주치). 4호 간격으로 모았으므로
신고 축은 4주 간격 표본이 된다. 이 사실을 CSV와 문서에 명시한다.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '12_신고_감시', 'data')


# 원문이 같은 질병을 여러 표기로 쓴다. 기계적으로 이으면 한 질병이 여러 계열로 쪼개진다.
# 표기 변경 자체는 아래 NAME_CHANGES에 사실로 남기고, 계열은 정식 명칭으로 합친다.
NAME_CANON = {
    '카바페넴내성장내세균 속균종(CRE) 감염증': '카바페넴내성장내세균목(CRE) 감염증',
    '카바페넴내성 장내세균목(CRE) 감염증': '카바페넴내성장내세균목(CRE) 감염증',
    '카바페넴내성장내세균목 (CRE) 감염증': '카바페넴내성장내세균목(CRE) 감염증',
    '반코마이신내성황색포도알균 (VRSA) 감염증': '반코마이신내성황색포도알균(VRSA) 감염증',
}
NAME_CHANGES = [
    {'canonical': '카바페넴내성장내세균목(CRE) 감염증',
     'variants': ['카바페넴내성장내세균 속균종(CRE) 감염증',
                  '카바페넴내성 장내세균목(CRE) 감염증',
                  '카바페넴내성장내세균목 (CRE) 감염증'],
     'note': "원문 표기가 2024년 중 '속균종'에서 '장내세균목'으로 바뀌었고 띄어쓰기도 흔들린다. "
             '표기 그대로 집계하면 한 질병이 세 계열로 쪼개진다.'},
]


def canon(name):
    return NAME_CANON.get(name, name)


def w(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        c = csv.writer(f)
        c.writerow(header)
        c.writerows(rows)
    print(f'  {os.path.relpath(path, ROOT)}  {len(rows)}행')


def main(paths):
    recs = []
    for p in paths:
        d = json.load(open(p, encoding='utf-8'))
        recs.extend(d if isinstance(d, list) else [d])
    recs = [r for r in recs if r.get('notifiable')]
    recs.sort(key=lambda r: (r['volume'] or 0, r['number'] or 0))
    print(f'입력 {len(recs)}개 호')

    # ── 전수감시 주간 신고 ────────────────────────────────────────────
    rows, imported = [], []
    for r in recs:
        n = r['notifiable']
        src = f"{r['volume']}-{r['number']}"
        for d in n['rows']:
            rows.append([n['year'], n['week'], n['as_of'], d['grade'], canon(d['disease']),
                         d['week_count'], d['cum'], d['avg5w'],
                         '' if d['avg5w'] in (None, 0) or d['week_count'] is None
                         else round(d['week_count'] / d['avg5w'], 2),
                         'Y' if d.get('partial_columns') else '', src])
            for i in d.get('imported', []):
                imported.append([n['year'], n['week'], canon(d['disease']), i['country'], i['n'], src])
    w(os.path.join(OUT, '전수감시_주간신고.csv'),
      ['연도', '주차', '기준일', '급', '감염병', '금주신고수', '연누계', '5년주별평균',
       '예년대비배수', '열부분추출', '출처호'], rows)
    w(os.path.join(OUT, '해외유입_신고국가.csv'),
      ['연도', '주차', '감염병', '유입국가', '신고수', '출처호'], imported)

    # ── 연도별 확정치(호마다 반복되므로 최신 호 기준으로 한 번만) ────
    ann = {}
    for r in recs:
        for d in r['notifiable']['rows']:
            for y, v in (d.get('by_year') or {}).items():
                ann[(canon(d['disease']), y)] = (v, f"{r['volume']}-{r['number']}")
    w(os.path.join(OUT, '연도별_확정신고수.csv'),
      ['감염병', '연도', '신고수', '출처호'],
      [[dz, y, v, s] for (dz, y), (v, s) in sorted(ann.items())])

    # ── 표본감시 ──────────────────────────────────────────────────────
    sent = []
    for r in recs:
        s = r.get('sentinel') or {}
        f = s.get('influenza') or {}
        h = s.get('hfmd') or {}
        e = s.get('eye') or {}
        sent.append([f.get('week'), f.get('as_of'), f.get('ili'), f.get('clinics'),
                     f.get('threshold'), h.get('week'), h.get('rate'), h.get('clinics'),
                     e.get('keratoconjunctivitis'), e.get('hemorrhagic'),
                     f"{r['volume']}-{r['number']}"])
    w(os.path.join(OUT, '표본감시_의사환자분율.csv'),
      ['인플루엔자_주차', '인플루엔자_기준일', 'ILI_1000명당', 'ILI_표본기관수', 'ILI_유행기준',
       '수족구_주차', '수족구_1000명당', '수족구_표본기관수',
       '유행성각결막염_1000명당', '급성출혈성결막염_1000명당', '출처호'], sent)

    sti = []
    for r in recs:
        s = (r.get('sentinel') or {}).get('sti')
        if not s:
            continue
        for k, v in s['per_clinic'].items():
            sti.append([s['week'], k, v, f"{r['volume']}-{r['number']}"])
    w(os.path.join(OUT, '성매개감염병_기관당신고.csv'),
      ['주차', '감염병', '보고기관당_신고수', '출처호'], sti)

    ob = [[(r.get('waterborne_outbreak') or {}).get('week'),
           (r.get('waterborne_outbreak') or {}).get('events'),
           (r.get('waterborne_outbreak') or {}).get('cases'),
           (r.get('waterborne_outbreak') or {}).get('cum_events'),
           (r.get('waterborne_outbreak') or {}).get('cum_cases'),
           f"{r['volume']}-{r['number']}"]
          for r in recs if r.get('waterborne_outbreak')]
    w(os.path.join(OUT, '수인성식품매개_집단발생.csv'),
      ['주차', '금주_건수', '금주_환자수', '누적_건수', '누적_환자수', '출처호'], ob)

    json.dump({'표기_통합': NAME_CANON, '표기_변경': NAME_CHANGES},
              open(os.path.join(OUT, '표기_원장.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f"  12_신고_감시/data/표기_원장.json  통합 {len(NAME_CANON)}건")

    weeks = sorted({(r['notifiable']['year'], r['notifiable']['week']) for r in recs})
    print(f"\n표본 주차 {len(weeks)}개: {weeks[0][0]}년 {weeks[0][1]}주 ~ {weeks[-1][0]}년 {weeks[-1][1]}주")
    print(f"감염병 {len({d['disease'] for r in recs for d in r['notifiable']['rows']})}종")


if __name__ == '__main__':
    main(sys.argv[1:])
