#!/usr/bin/env python3
"""⑱ 예방접종 — 접종률 원장과 집단면역 문턱 대조

접종률을 목록으로 보여 주는 쪽은 이미 질병관리청에 있다. 여기서 더할 것은 세 가지다.

 1. **'완전'의 뜻이 해마다 바뀐다.** 2017년 9종이던 완전접종 기준이 2025년 13종이다.
    분모가 아니라 '완전'의 정의가 움직였으므로 연도를 그냥 이으면 안 된다.
 2. **집단면역 문턱과 나란히 놓는다.** Vc = (1 − 1/R₀) / VE. ⑰ 시뮬레이터의 R₀를 그대로 쓴다.
    백일해·수두는 이 값이 100%를 넘는다 — 접종만으로는 유행을 못 막는다는 뜻이다.
 3. **접종률과 발생수를 같은 그림에.** 2024년 백일해 164.5배는 접종률이 떨어져서가 아니다.

산출: portal/vaccine/index.html
"""
import csv
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D18 = os.path.join(ROOT, '18_예방접종', 'data')
RATES = os.path.join(D18, '어린이_예방접종률.json')
LINK = os.path.join(D18, '백신_감염병_연결.json')
SIM = os.path.join(ROOT, '17_유행_시뮬레이터', 'data', '모형_매개변수.json')
CASES = os.path.join(ROOT, '03_백서_정리', 'data', '전수감시_신고수_2016_2025.csv')
TPL = os.path.join(ROOT, 'scripts', 'templates', 'vaccine.template.html')
OUT = os.path.join(ROOT, 'portal', 'vaccine', 'index.html')

AGE_ORDER = ['1세', '2세', '3세', '6세', '13세']
# 접종 차수를 다 마치는 나이. 문턱과 견줄 '실제 접종률'은 이 나이의 값을 쓴다.
DONE_AGE = {'Tdap': '13세', 'RV': '2세', 'BCG': '1세'}
DEFAULT_DONE = '6세'


def coverage(j):
    rate = defaultdict(lambda: defaultdict(dict))     # 연령 → 백신 → 연도 → 값
    for r in j['rows']:
        if r['항목'] != '접종률' or r.get('이상'):
            continue
        rate[r['연령']][r['백신']][r['연도']] = r['값']
    return rate


def build():
    j = json.load(open(RATES, encoding='utf-8'))
    link = json.load(open(LINK, encoding='utf-8'))
    sim = json.load(open(SIM, encoding='utf-8'))
    rate = coverage(j)
    years = sorted({r['연도'] for r in j['rows']})
    ages = [a for a in AGE_ORDER if a in rate]

    # ── 완전접종률 추이 ────────────────────────────────────────────
    complete = {a: [rate[a].get('완전접종률', {}).get(y) for y in years] for a in ages}

    # ── '완전'의 정의 변화 ────────────────────────────────────────
    defs = []
    for e in sorted(j['editions'], key=lambda e: e['year']):
        vs = [v for v in e['vaccines'] if v != '완전접종률']
        defs.append({'year': e['year'], 'n': len(vs), 'vaccines': vs, 'ages': e['ages']})
    for i, d in enumerate(defs):
        prev = set(defs[i - 1]['vaccines']) if i else set()
        d['added'] = sorted(set(d['vaccines']) - prev) if i else []

    # ── 집단면역 문턱 ─────────────────────────────────────────────
    r0 = {x['name']: x['r0'] for x in sim['diseases']}
    over = link['disease_ve_override']
    rows = []
    for v in link['vaccines']:
        for dz in v['diseases']:
            if dz not in r0:
                continue                       # R₀를 모르는 병은 계산하지 않는다
            ve = over.get(dz, {}).get('ve', v['ve'])
            lo, hi = r0[dz]
            vc = [100 * (1 - 1 / lo) / ve, 100 * (1 - 1 / hi) / ve]
            age = DONE_AGE.get(v['code'], DEFAULT_DONE)
            series = rate.get(age, {}).get(v['code'], {})
            act_y = max(series) if series else None
            act = series.get(act_y)
            verdict = ('impossible' if vc[0] > 100 else
                       'none' if act is None else
                       'over' if act >= vc[1] else
                       'edge' if act >= vc[0] else 'under')
            # 백일해는 소아용(DTaP)과 청소년 추가접종(Tdap)이 따로 있다. 같은 병이지만
            # 백신 효과가 달라 문턱도 달라지므로 두 줄로 놓고 이름에 표시한다.
            label = dz if v['code'] != 'Tdap' else f'{dz}(청소년 추가접종)'
            rows.append({
                'disease': dz, 'label': label, 'vaccine': v['code'], 'vname': v['name'],
                'r0': [lo, hi], 've': round(ve, 3),
                've_note': over.get(dz, {}).get('note', v['ve_note']),
                'src': over.get(dz, {}).get('src', v['src']),
                'vc': [round(vc[0], 1), round(vc[1], 1)],
                'actual': act, 'actual_age': age, 'actual_year': act_y,
                'verdict': verdict,
            })
    order = {'impossible': 0, 'under': 1, 'edge': 2, 'over': 3, 'none': 4}
    rows.sort(key=lambda r: (order[r['verdict']], -r['vc'][1]))

    # ── 발생수(전수감시) ──────────────────────────────────────────
    want = {r['disease'] for r in rows}
    cyears, cseries = [], {}
    for r in csv.DictReader(open(CASES, encoding='utf-8-sig')):
        if r['감염병명'] not in want:
            continue
        if not cyears:
            cyears = [int(k) for k in r if k.isdigit()]
        cseries[r['감염병명']] = [int(r[str(y)]) if r[str(y)].strip().isdigit() else None
                               for y in cyears]

    data = {
        'as_of': j['as_of'], 'source': j['source'],
        'years': years, 'ages': ages,
        'complete': complete,
        'byvacc': {a: {v: [rate[a][v].get(y) for y in years]
                       for v in sorted(rate[a]) if v != '완전접종률'} for a in ages},
        'defs': defs,
        'threshold': rows,
        'threshold_note': link['threshold_note'],
        'cases': {'years': cyears, 'series': cseries},
        'anomalies': j.get('anomalies', []),
        'skipped': j.get('skipped', []),
    }
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = open(TPL, encoding='utf-8').read().replace('__DATA__', js)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)

    imp = sorted({r['disease'] for r in rows if r['verdict'] == 'impossible'})
    print(f'예방접종 — {years[0]}~{years[-1]}년 · 연령 {len(ages)} · 문턱 계산 {len(rows)}종')
    print(f'  접종만으로 문턱을 못 넘는 감염병: {", ".join(imp) if imp else "없음"}')
    for r in rows[:6]:
        a = f"{r['actual']:.1f}%" if r['actual'] is not None else '—'
        print(f"    {r['disease']:8s} R₀ {r['r0'][0]}~{r['r0'][1]} · VE {r['ve']:.2f} → "
              f"필요 {r['vc'][0]:.1f}~{r['vc'][1]:.1f}% · 실제({r['actual_age']}) {a} [{r['verdict']}]")
    print(f'  → {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,}B)')


if __name__ == '__main__':
    build()
