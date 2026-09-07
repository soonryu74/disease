#!/usr/bin/env python3
"""신고 축 × 검출 축 × 검역 축 교차 분석 → 13_교차검증/data/ + portal/cross/

이 저장소가 질병관리청 주간 보고서와 다른 지점은 '숫자'가 아니라 '숫자끼리의 대조'다.
세 가지를 만든다.

 1. **이례 신고 순위** — 금주 신고수 ÷ 5년 주별 평균. 원문은 이번 주 한 점만 보여주지만
    여기서는 3년치 곡선으로 언제 시작해 언제 꺼졌는지를 본다.
 2. **신고 ↔ 검출 대조** — 같은 주의 신고 지표와 병원체 검출 지표를 나란히 놓는다.
    같이 움직이면 유행 신호, 신고만 움직이면 신고 행태·제도 변화를 의심한다.
 3. **해외유입 ↔ 검역 지정 대조** — 실제 유입 신고가 있었던 국가가 검역관리지역으로
    지정돼 있었는지. 지정이 유입을 앞서는지 따라가는지 본다.
"""
import csv
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(ROOT, '12_신고_감시', 'data')
LAB = os.path.join(ROOT, '10_진단검사_감시', 'data')
QUAR = os.path.join(ROOT, '11_검역관리지역', 'data')
OUT = os.path.join(ROOT, '13_교차검증', 'data')

MIN_PAIRS = 8          # 이보다 적으면 상관을 계산하지 않고 '판단 유보'
MIN_BASE = 3.0         # 5년 평균이 이보다 작으면 배수는 불안정 → 순위에서 제외

# 신고 축 ↔ 검출 축 짝. 같은 것을 세지 않는다는 점을 note에 적는다.
PAIRS = [
    {'key': 'influenza', 'label': '인플루엔자',
     'report': ('sentinel', 'ILI_1000명당'), 'report_label': '의사환자분율(외래 1,000명당)',
     'lab': ('resp', '인플루엔자'), 'lab_label': '인플루엔자 바이러스 검출률(%)',
     'note': '신고 축은 증상 기반(의사환자), 검출 축은 검사 확인이다. ILI가 오르는데 검출률이 '
             '따라 오르지 않으면 다른 호흡기 바이러스이거나 진료 행태 변화일 수 있다.'},
    {'key': 'hfmd', 'label': '수족구병',
     'report': ('sentinel', '수족구_1000명당'), 'report_label': '의사환자분율(외래 1,000명당)',
     'lab': ('entero', '수족구병_포진성구협염'), 'lab_label': '엔테로바이러스 검출 건수',
     'note': '검출 축은 건수(비율 아님)라 표본 크기 변화에 민감하다.'},
    {'key': 'shigella', 'label': '세균성이질',
     'report': ('notifiable', '세균성이질'), 'report_label': '전수 신고수(주)',
     'lab': ('diarb', '세균성이질'), 'lab_label': '분리율(%)',
     'note': '전수 신고와 표본 검사실 분리율. 분모가 서로 달라 값의 크기가 아니라 방향을 본다.'},
    {'key': 'ehec', 'label': '장출혈성대장균감염증',
     'report': ('notifiable', '장출혈성대장균감염증'), 'report_label': '전수 신고수(주)',
     'lab': ('diarb', '병원성대장균'), 'lab_label': '병원성대장균 분리율(%)',
     'note': '검출 축의 병원성대장균은 장출혈성대장균보다 넓은 범주다. 같은 것을 세지 않는다.'},
    {'key': 'salmonella', 'label': '장티푸스·파라티푸스',
     'report': ('notifiable', '장티푸스+파라티푸스'), 'report_label': '전수 신고수 합(주)',
     'lab': ('diarb', '살모넬라'), 'lab_label': '살모넬라 분리율(%)',
     'note': '검출 축의 살모넬라는 비장티푸스성을 포함한다. 범주가 넓다.'},
    {'key': 'vibrio', 'label': '비브리오패혈증',
     'report': ('notifiable', '비브리오패혈증'), 'report_label': '전수 신고수(주)',
     'lab': ('diarb', '장염비브리오'), 'lab_label': '장염비브리오 분리율(%)',
     'note': '원인균이 다르다(패혈증 V. vulnificus / 장염 V. parahaemolyticus). 계절만 공유한다.'},
    {'key': 'cholera', 'label': '콜레라',
     'report': ('notifiable', '콜레라'), 'report_label': '전수 신고수(주)',
     'lab': ('diarb', '비브리오콜레라'), 'lab_label': '비브리오콜레라 분리율(%)',
     'note': '두 축 모두 0이 대부분이라 상관이 의미를 갖기 어렵다.'},
]


def rd(path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def spearman(xs, ys):
    """순위상관. 동점은 평균 순위."""
    n = len(xs)
    if n < 3:
        return None

    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num_ = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return None if den == 0 else round(num_ / den, 3)


def verdict(rho, n):
    if n < MIN_PAIRS or rho is None:
        return 'hold', f'짝지어진 주가 {n}개뿐이라 판단을 보류한다'
    if rho >= 0.5:
        return 'agree', '두 축이 같은 방향으로 움직인다 — 유행 신호로 읽을 근거가 있다'
    if rho >= 0.2:
        return 'weak', '방향은 같지만 약하다 — 한쪽만으로 판단하면 위험하다'
    if rho <= -0.2:
        return 'oppose', '두 축이 반대로 움직인다 — 정의·분모·신고 행태를 먼저 의심해야 한다'
    return 'none', '두 축이 따로 논다 — 신고 증감을 유행 증감으로 읽으면 안 된다'


def build():
    os.makedirs(OUT, exist_ok=True)
    notif = rd(os.path.join(REP, '전수감시_주간신고.csv'))
    sent = rd(os.path.join(REP, '표본감시_의사환자분율.csv'))
    resp = rd(os.path.join(LAB, '호흡기바이러스_주간검출률.csv'))
    diarb = rd(os.path.join(LAB, '급성설사세균_주간분리.csv'))
    entero = rd(os.path.join(LAB, '엔테로바이러스_주간검출.csv'))

    # ── 축별 조회표 ──────────────────────────────────────────────────
    rep_by = defaultdict(dict)      # 감염병 → (연,주) → 신고수
    base_by = defaultdict(dict)     # 감염병 → (연,주) → (금주, 5년평균, 배수)
    for r in notif:
        k = (int(r['연도']), int(r['주차']))
        v = num(r['금주신고수'])
        if v is not None:
            rep_by[r['감염병']][k] = v
        a, c = num(r['5년주별평균']), num(r['금주신고수'])
        if a and c is not None:
            base_by[r['감염병']][k] = (c, a, round(c / a, 2))
    # 합산 계열
    for k in set(rep_by['장티푸스']) | set(rep_by['파라티푸스']):
        a, b = rep_by['장티푸스'].get(k), rep_by['파라티푸스'].get(k)
        if a is not None or b is not None:
            rep_by['장티푸스+파라티푸스'][k] = (a or 0) + (b or 0)

    sent_by = {}
    for r in sent:
        for wk_col, cols in (('인플루엔자_주차', ('ILI_1000명당',)),
                             ('수족구_주차', ('수족구_1000명당',))):
            w = r.get(wk_col)
            if not w:
                continue
            y = (r.get('인플루엔자_기준일') or '')[:4]
            if not y.isdigit():
                continue
            for c in cols:
                v = num(r.get(c))
                if v is not None:
                    sent_by.setdefault(c, {})[(int(y), int(w))] = v

    lab_by = {'resp': defaultdict(dict), 'diarb': defaultdict(dict), 'entero': defaultdict(dict)}
    for r in resp:
        k = (int(r['연도']), int(r['주차']))
        for c in ('인플루엔자', '코로나19', 'RSV', '리노'):
            v = num(r.get(c))
            if v is not None:
                lab_by['resp'][c][k] = v
    for r in diarb:
        k = (int(r['연도']), int(r['주차']))
        for c in ('세균성이질', '병원성대장균', '살모넬라', '장염비브리오', '비브리오콜레라'):
            v = num(r.get(c + '_분리율'))
            if v is not None:
                lab_by['diarb'][c][k] = v
    for r in entero:
        k = (int(r['연도']), int(r['주차']))
        v = num(r.get('수족구병_포진성구협염'))
        if v is not None:
            lab_by['entero']['수족구병_포진성구협염'][k] = v

    def series(axis, name):
        if axis == 'notifiable':
            return rep_by.get(name, {})
        if axis == 'sentinel':
            return sent_by.get(name, {})
        return lab_by[axis].get(name, {})

    # ── 1) 신고 ↔ 검출 대조 ─────────────────────────────────────────
    pairs_out = []
    for p in PAIRS:
        rs = series(*p['report'])
        ls = series(*p['lab'])
        # 같은 호 안에서도 표마다 기준 주차가 다르다(예: 수족구 35주 / 엔테로 34주).
        # 정확히 같은 주가 없으면 ±1주까지 짝을 허용하고, 그 사실을 tolerance로 남긴다.
        common, tol_used = [], 0
        for k in sorted(rs):
            if k in ls:
                common.append((k, k))
            else:
                alt = [(k[0], k[1] + o) for o in (-1, 1) if (k[0], k[1] + o) in ls]
                if alt:
                    common.append((k, alt[0]))
                    tol_used += 1
        xs = [rs[a] for a, _ in common]
        ys = [ls[b] for _, b in common]
        rho = spearman(xs, ys) if len(common) >= 3 else None
        v, why = verdict(rho, len(common))
        if tol_used:
            why += f' (짝 {tol_used}개는 ±1주 차이로 맞췄다)'
        pairs_out.append({
            'key': p['key'], 'label': p['label'], 'note': p['note'],
            'report_label': p['report_label'], 'lab_label': p['lab_label'],
            'n_paired': len(common), 'rho': rho, 'verdict': v, 'why': why,
            'report': [{'t': f'{y}-{w:02d}', 'v': rs[(y, w)]} for y, w in sorted(rs)],
            'lab': [{'t': f'{y}-{w:02d}', 'v': ls[(y, w)]} for y, w in sorted(ls)],
            'tolerance_used': tol_used,
            'paired': [{'t': f'{a[0]}-{a[1]:02d}', 'r': rs[a], 'l': ls[b]} for a, b in common],
        })

    # ── 2) 이례 신고 순위 ───────────────────────────────────────────
    anomalies = []
    for dz, m in base_by.items():
        pts = [(k, v) for k, v in sorted(m.items()) if v[1] >= MIN_BASE]
        if not pts:
            continue
        peak = max(pts, key=lambda t: t[1][2])
        anomalies.append({
            'disease': dz, 'peak_ratio': peak[1][2],
            'peak_week': f'{peak[0][0]}-{peak[0][1]:02d}',
            'peak_count': peak[1][0], 'peak_base': peak[1][1],
            'series': [{'t': f'{k[0]}-{k[1]:02d}', 'ratio': v[2], 'n': v[0], 'base': v[1]}
                       for k, v in pts],
        })
    anomalies.sort(key=lambda a: -a['peak_ratio'])

    # ── 3) 해외유입 ↔ 검역 지정 ─────────────────────────────────────
    imp = rd(os.path.join(REP, '해외유입_신고국가.csv'))
    q = json.load(open(os.path.join(QUAR, '2026Q3_지정내역.json'), encoding='utf-8'))
    pri = set()
    for cs in q['중점_감염병별_국가'].values():
        pri.update(cs)
    gen = set()
    with open(os.path.join(QUAR, '2026Q3_검역관리지역.csv'), encoding='utf-8') as f:
        rr = csv.reader(f)
        next(rr)
        for row in rr:
            gen.add(row[0])
    by_country = defaultdict(lambda: {'n': 0, 'diseases': defaultdict(int)})
    for r in imp:
        c = r['유입국가']
        by_country[c]['n'] += int(r['신고수'])
        by_country[c]['diseases'][r['감염병']] += int(r['신고수'])
    inflow = [{'country': c, 'n': d['n'],
               'diseases': dict(sorted(d['diseases'].items(), key=lambda t: -t[1])),
               'priority': c in pri, 'general': c in gen}
              for c, d in sorted(by_country.items(), key=lambda t: -t[1]['n'])]

    findings = [
        {'title': "질병관리청 원문 오기 — '온두리스'",
         'body': "2024년 43주 뎅기열 해외유입 국가로 '온두리스'가 실렸다. 정식 국가명은 '온두라스'다. "
                 '국가명으로 집계하면 이 건이 별도 국가로 빠진다.',
         'evidence': '주간 건강과 질병 17권 42호 1쪽 — 뎅기열 행: 라오스(1), 온두리스(1)'},
        {'title': 'CRE 표기가 3년 사이 세 번 바뀌었다',
         'body': "'카바페넴내성장내세균 속균종(CRE) 감염증'(~2024년 18주) → '카바페넴내성 장내세균목"
                 "(CRE) 감염증'(2024년 22주~) → '카바페넴내성장내세균목 (CRE) 감염증'(2025년 1주~). "
                 '분류학 개정과 띄어쓰기 변동이 겹쳤다. 표기 그대로 집계하면 한 질병이 세 계열로 쪼개진다. '
                 '이 저장소는 정식 명칭으로 합치고 변경 사실을 표기 원장에 남긴다.',
         'evidence': '12_신고_감시/data/표기_원장.json'},
        {'title': '같은 호 안에서도 표마다 기준 주차가 다르다',
         'body': '한 호 안에서 인플루엔자·호흡기바이러스는 35주차, 급성설사·엔테로바이러스는 34주차 기준인 '
                 '식이다. 두 표의 숫자를 같은 주로 놓고 비교하면 한 주씩 어긋난다. '
                 '이 페이지는 정확히 같은 주가 없을 때만 ±1주 짝을 허용하고 그 개수를 각 쌍에 적었다.',
         'evidence': '19권 34호 — II장 수족구 35주차 / VI장 엔테로바이러스 34주차'},
        {'title': '신규 편입 질병은 표의 열 수가 다르다',
         'body': "매독·엠폭스처럼 최근 전수감시로 편입된 질병은 '5년 주별 평균' 칸이 아예 비어 있어 "
                 '추출되는 열 수가 다른 질병보다 적다. 위치만 보고 열을 맞추면 연도별 값이 한 칸씩 밀린다. '
                 '이 저장소는 위치가 확정적인 앞 두 칸(금주·누계)만 신뢰하고 나머지는 비워 둔다.',
         'evidence': "18권 14호 — '매독 32 573 2,794' (열 3개), 다른 질병은 8개"},
    ]

    data = {
        'built_from': {'신고 표본 주차': len({(int(r['연도']), int(r['주차'])) for r in notif}),
                       '검출 주차': len({(int(r['연도']), int(r['주차'])) for r in resp}),
                       '검역 기준': q['기준']},
        'pairs': pairs_out, 'anomalies': anomalies, 'inflow': inflow, 'findings': findings,
        'min_pairs': MIN_PAIRS, 'min_base': MIN_BASE,
    }
    json.dump(data, open(os.path.join(OUT, '교차검증.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f"→ 13_교차검증/data/교차검증.json")
    print(f"  대조쌍 {len(pairs_out)} · 이례 후보 {len(anomalies)} · 유입국가 {len(inflow)}")
    for p in pairs_out:
        print(f"   {p['label']:<16} n={p['n_paired']:>3} ρ={p['rho']} → {p['verdict']}")
    print('  이례 상위:', [(a['disease'], a['peak_ratio']) for a in anomalies[:5]])
    unlisted = [i for i in inflow if not i['priority'] and not i['general']]
    print(f"  유입 신고국 중 검역관리지역 미지정: {len(unlisted)}개국",
          [i['country'] for i in unlisted[:8]])

    # 페이지 조립
    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'cross.template.html'),
                encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    dst = os.path.join(ROOT, 'portal', 'cross', 'index.html')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    print(f'→ portal/cross/index.html  {os.path.getsize(dst):,}B')


if __name__ == '__main__':
    build()
