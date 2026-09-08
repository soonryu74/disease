#!/usr/bin/env python3
"""⑰ 유행 시뮬레이터 → portal/sim/

모형 매개변수(17_유행_시뮬레이터/data/모형_매개변수.json)에 ⑤ 도감의 잠복기·전파경로와
⑨ 연대기의 현행 급·격리 지위를 붙여 템플릿에 넣는다. SEIR 계산은 브라우저에서 한다.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from build_field_page import dogam_fields, norm, current_phase  # noqa: E402

SRC = os.path.join(ROOT, '17_유행_시뮬레이터', 'data', '모형_매개변수.json')
OUT = os.path.join(ROOT, 'portal', 'sim', 'index.html')


def parse_incubation(s):
    """'7~21일(흔히 10~12일)' → (7, 21, 11). 대표값은 괄호 안 범위의 중앙, 없으면 범위 중앙."""
    if not s:
        return None
    nums = lambda t: [float(x) for x in re.findall(r'\d+(?:\.\d+)?', t)]  # noqa: E731
    paren = re.search(r'\(([^)]*(?:흔히|보통|대개|평균|통상)[^)]*)\)', s)
    body = re.sub(r'\([^)]*\)', '', s)
    rng = nums(body.split('(')[0])
    if '시간' in body and '일' not in body.split('~')[0]:
        rng = [x / 24 for x in rng]
    lo, hi = (rng[0], rng[1]) if len(rng) >= 2 else ((rng[0], rng[0]) if rng else (None, None))
    typ = None
    if paren:
        pn = nums(paren.group(1))
        if pn:
            typ = sum(pn[:2]) / len(pn[:2])
    if typ is None and lo is not None:
        typ = (lo + hi) / 2
    return {'lo': lo, 'hi': hi, 'typ': round(typ, 1) if typ else None, 'text': s}


def build():
    P = json.load(open(SRC, encoding='utf-8'))
    dog = dogam_fields()
    chron = json.load(open(os.path.join(ROOT, '09_감염병연대기', 'data', '연대기.json'), encoding='utf-8'))
    phase = {norm(d['name']): current_phase(d) for d in chron['diseases']}
    out = []
    for d in P['diseases']:
        k = norm(d['name'])
        dg = dog.get(k) or next((v for kk, v in dog.items() if kk.startswith(k[:6])), {})
        ph = phase.get(k) or next((v for kk, v in phase.items() if kk.startswith(k[:6])), {})
        inc = parse_incubation(dg.get('잠복기'))
        if inc and inc['lo'] is not None and inc['lo'] == inc['hi']:
            inc = None  # '최대 약 14일'처럼 값이 하나뿐이면 대표값을 잡을 수 없다
        if (not inc or not inc['typ']) and d.get('incubation_fallback'):
            inc = parse_incubation(d['incubation_fallback'])
            inc['fallback'] = d.get('incubation_fallback_src', '')
        if not inc or not inc['typ']:
            raise SystemExit(f"{d['name']}: 도감 잠복기를 숫자로 읽지 못함 — {dg.get('잠복기')!r}")
        out.append(dict(d, incubation=inc, route=dg.get('감염경로'), grade=ph.get('status'), iso=ph.get('iso'),
                        report=ph.get('report')))
    # 실제 기록: ③ 연보 기반 전수감시 신고수 2016~2025 — 모형이 실제와 얼마나 다른지 눈으로 보게
    annual = {}
    import csv
    yb = os.path.join(ROOT, '03_백서_정리', 'data', '전수감시_신고수_2016_2025.csv')
    for r in csv.DictReader(open(yb, encoding='utf-8-sig')):
        nm = norm(re.sub(r'\([A-Za-z0-9\-]+\)', '', r['감염병명']))
        years = {y: r[y] for y in map(str, range(2016, 2026)) if r.get(y) not in (None, '', '-')}
        if not years:
            continue
        cur = annual.setdefault(nm, {'years': {}, 'note': r.get('비고', '')})
        for y, v in years.items():
            cur['years'][y] = int(v.replace(',', ''))
        if r.get('비고'):
            cur['note'] = r['비고']
    for d in out:
        k = norm(d['name'])
        d['annual'] = annual.get(k) or next((v for kk, v in annual.items() if kk.startswith(k[:6])), None)
    data = {'diseases': out, 'defaults': P['intervention_defaults'], 'about': P['_about'],
            'references': P.get('references', {}), 'scenario_provenance': P.get('scenario_provenance', ''),
            'population': 51_700_000,
            'population_note': '전국 인구 어림값. 정확한 연도별 추계는 이 저장소에 수집돼 있지 않다.',
            'annual_source': '③ 백서 정리 · 연보 기반 전수감시 신고수 2016~2025'}
    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'sim.template.html'), encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    print(f"→ portal/sim/index.html  {os.path.getsize(OUT):,}B")
    for d in out:
        print(f"  {d['name']:<14} R0 {d['r0'][0]}–{d['r0'][1]} · 잠복 {d['incubation']['typ']}일 · 전염 {d['d_inf']}일 · 증상전 {d['presym']}일 · {d['grade']} {d['iso']}")


if __name__ == '__main__':
    build()
