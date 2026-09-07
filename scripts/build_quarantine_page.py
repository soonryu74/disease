#!/usr/bin/env python3
"""11_검역관리지역 데이터 → portal/quarantine/index.html."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, '11_검역관리지역', 'data')
OUT = os.path.join(ROOT, 'portal', 'quarantine', 'index.html')


def build():
    hist = json.load(open(os.path.join(DATA, '지정이력.json'), encoding='utf-8'))
    cur = json.load(open(os.path.join(DATA, '2026Q3_지정내역.json'), encoding='utf-8'))
    q3 = json.load(open(os.path.join(ROOT, '11_검역관리지역', 'data', '2026Q3_지정내역.json'),
                        encoding='utf-8'))

    # 국가 → {중점:[], 검역:[]}
    pri = cur['중점_감염병별_국가']
    countries = {}
    for dis, cs in pri.items():
        for c in cs:
            countries.setdefault(c, {'p': [], 'g': []})['p'].append(dis)

    # 검역관리지역 매트릭스 CSV에서 국가별 감염병
    import csv
    with open(os.path.join(DATA, '2026Q3_검역관리지역.csv'), encoding='utf-8') as f:
        rd = csv.reader(f)
        head = next(rd)[1:]
        for row in rd:
            c = row[0]
            ds = [head[i] for i, v in enumerate(row[1:]) if v.strip()]
            countries.setdefault(c, {'p': [], 'g': []})['g'] = ds

    data = {
        'as_of': hist['as_of'],
        'definitions': hist['definitions'],
        'legal_basis': hist['legal_basis'],
        'breaks': hist['structural_breaks'],
        'periods': hist['periods'],
        'matched': hist['matched_context'],
        'unverified': hist['unverified'],
        'current': {'기준': q3['기준'], '출처': q3['출처'], '과태료': q3.get('과태료'),
                    'priority': pri, 'sub': q3.get('중점_지역세부', {}),
                    'general_counts': q3['검역_감염병별_국가수']},
        'countries': countries,
    }
    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'quarantine.template.html'),
                encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    print(f'→ portal/quarantine/index.html  {os.path.getsize(OUT):,}B '
          f'(국가 {len(countries)} · 시기 {len(hist["periods"])} · 단절점 {len(hist["structural_breaks"])})')


if __name__ == '__main__':
    build()
