#!/usr/bin/env python3
"""⑮ 해외유입 지도 → portal/inflow/

네 갈래를 나라(ISO3) 하나로 묶는다.
 - 얼마나 들어오나   국토부 노선별 도착여객(직항) · 법무부 국적별 입국자
 - 무엇을 막으라 했나 ⑪ 검역관리지역·중점검역관리지역 (2026Q3)
 - 실제로 무엇이 들어왔나 ⑫ 해외유입 신고 국가 (PHWR 표본 호)
 - 어디에 그리나     Natural Earth 110m

그리고 KDCA가 내놓지 않는 숫자 하나를 만든다:
    유입 신고 건수 ÷ 들어온 사람 수  = 나라별 유입 위험도
분모가 둘(노선·국적)이라 둘 다 낸다. 어긋나는 나라는 그 어긋남이 정보다.
"""
import csv
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D15 = os.path.join(ROOT, '15_해외유입_지도', 'data')
D11 = os.path.join(ROOT, '11_검역관리지역', 'data')
D12 = os.path.join(ROOT, '12_신고_감시', 'data')
OUT = os.path.join(ROOT, 'portal', 'inflow', 'index.html')

ICN = [126.45, 37.46]
# 분모 기간: 항공 통계가 있는 구간. 신고 표본이 2023-52주~2026-35주라 거의 겹친다.
PERIOD = ('2024-01', '2026-07')

# 우리 자료의 이름 → ISO3. Natural Earth 한글명으로 못 잡는 것만 적는다.
ALIAS = {
    '중국': 'CHN', '대만': 'TWN', '타이완': 'TWN', '타이': 'THA', '호주': 'AUS',
    '홍콩': 'HKG', '마카오': 'MAC', '싱가포르': 'SGP', '러시아연방': 'RUS',
    '러시아(연방)': 'RUS', '남수단공화국': 'SSD', '예멘공화국': 'YEM',
    '아랍에미레이트': 'ARE', '아랍에미리트연합': 'ARE', '튀르키예': 'TUR', '포르투칼': 'PRT',
    '슬로바크': 'SVK', '키르기즈': 'KGZ', '키르기즈스탄': 'KGZ', '투르크매니스탄': 'TKM',
    '벨로루시': 'BLR', '마케도니아': 'MKD', '콩고': 'COG', '온두리스': 'HND',
    '에스트레아': 'ERI', '요만': 'OMN', '몰디브': 'MDV', '바레인': 'BHR', '몰타': 'MLT',
    '모리셔스': 'MUS', '세이셸': 'SYC', '세이셀': 'SYC', '카보베르데': 'CPV', '코모로': 'COM',
    '상투메프린시페': 'STP', '괌': 'GUM', '사이판': 'MNP', '팔라우': 'PLW',
    '티모르민주공화국': 'TLS', '보스니아-헤르체고비나': 'BIH', '미크로네시아': 'FSM',
    '마이크로네시아': 'FSM', '미이크로네시아': 'FSM', '마샬군도': 'MHL', '솔로몬군도': 'SLB',
    '뉴칼레도니아': 'NCL', '폴리네시아': 'PYF', '통가': 'TON', '사모아': 'WSM', '나우루': 'NRU',
    '투발루': 'TUV', '키리바시': 'KIR', '쿡제도': 'COK', '안도라': 'AND', '모나코': 'MCO',
    '리히텐슈타인': 'LIE', '산마리노': 'SMR', '교황청': 'VAT', '바베이도스': 'BRB',
    '그레나다': 'GRD', '도미니카연방': 'DMA', '세인트루시아': 'LCA',
    '세인트빈센트그레나딘': 'VCT', '세인트키츠네비스': 'KNA', '세인트크리스토퍼네비스': 'KNA',
    '앤티가': 'ATG', '앤티카바부다': 'ATG', '프랑스령기아나': 'GUF', '과들루프': 'GLP',
    '마르티니크': 'MTQ', '레위니옹': 'REU', '마요트': 'MYT', '아루바': 'ABW',
    '신트마르턴': 'SXM', '세인트마틴': 'MAF', '생바르텔르미': 'BLM', '앵귈라': 'AIA',
    '영국령버진아일랜드': 'VGB', '영령버진아일랜드': 'VGB', '미국령버진아일랜드': 'VIR',
    '터크스케이커스': 'TCA', '토켈라우': 'TKL', '왈리스푸투나': 'WLF', '노퍽': 'NFK',
    '하와이': 'USA', '영령인도양섬': 'IOT', '한국': 'KOR', '대한민국': 'KOR',
}
# 화면 표기. Natural Earth 한글명이 공식 국호라 길다. 우리 자료(KDCA·법무부)의 표기를 따른다.
DISPLAY = {'CHN': '중국', 'TWN': '대만', 'PRK': '북한', 'ZAF': '남아프리카공화국',
           'DOM': '도미니카공화국', 'CAF': '중앙아프리카공화국', 'COD': '콩고민주공화국',
           'COG': '콩고공화국', 'GNQ': '적도기니', 'BIH': '보스니아헤르체고비나',
           'TTO': '트리니다드토바고', 'NCL': '뉴칼레도니아'}
# 나라가 아닌 줄. 표에는 남기고 지도에는 안 올린다.
NOT_A_COUNTRY = {'기타', '총계', '전체합계', '유고슬라비아', '영국보호민', '영국속령지시민',
                 '영국외지민', '영국해외영토시민', '한국계러시아인', '한국계중국인', '홍콩거주난민',
                 '미국인근섬', '무국적'}
# KDCA 원문 오기. ⑬에서 이미 잡아 둔 것. 표기는 원문대로 두고 ISO만 바로 잡는다.
TYPO = {'온두리스': '온두라스'}
# 검역감염병 15종 (2026Q3 검역관리지역 고시의 열). 유입 신고에는 매독·수두처럼 검역 대상이
# 아닌 병이 훨씬 많다. '지정 안 했는데 들어왔다'는 비교는 이 15종 안에서만 성립한다.
QUAR_DISEASES = {'동물인플루엔자인체감염증', '에볼라바이러스병', '중동호흡기증후군', '페스트', '콜레라',
                 '황열', '마버그열', '라싸열', '크리미안콩고출혈열', '폴리오', '홍역', '뎅기열',
                 '치쿤구니야열', '지카바이러스감염증', '니파바이러스감염증'}


def norm_dz(s):
    return re.sub(r'[\s()·・\-]', '', s or '')


def norm(s):
    return re.sub(r'[\s()·・\-]', '', s or '')


def load_map():
    m = json.load(open(os.path.join(D15, '세계지도.json'), encoding='utf-8'))
    by_iso, ko2iso = {}, {}
    for c in m['countries'] + m['points']:
        by_iso[c['iso']] = c
        ko2iso[norm(c['ko'])] = c['iso']
    return m, by_iso, ko2iso


def make_resolver(ko2iso):
    unresolved = set()

    def iso(name):
        n = norm(name)
        if n in NOT_A_COUNTRY:
            return None
        r = ko2iso.get(n) or ALIAS.get(n) or ALIAS.get(name)
        if not r:
            unresolved.add(name)
        return r
    return iso, unresolved


def in_period(ym):
    return PERIOD[0] <= ym <= PERIOD[1]


def load_moj(iso):
    """법무부: 월별 국적별 외국인 입국자. 기간 합계와 월 시계열."""
    total, series, unmapped_total = defaultdict(int), defaultdict(dict), 0
    months = set()
    for r in csv.DictReader(open(os.path.join(D15, '법무부_국적별_입국자.csv'), encoding='utf-8')):
        ym = f"{r['년']}-{r['월'].zfill(2)}"
        months.add(ym)
        n = int(r['입국자수'].replace(',', '') or 0)
        k = iso(r['국적지역'])
        if not k:
            if in_period(ym):
                unmapped_total += n
            continue
        series[k][ym] = series[k].get(ym, 0) + n
        if in_period(ym):
            total[k] += n
    return total, series, sorted(months), unmapped_total


def load_air(iso):
    """국토부: 연도별 국가별 도착여객(전체·환승). 직항 노선이 있는 나라만 있다."""
    air = defaultdict(lambda: {'flights': 0, 'total': 0, 'transit': 0, 'years': {}})
    for r in csv.DictReader(open(os.path.join(D15, '국토부_국가별_도착여객.csv'), encoding='utf-8')):
        k = iso(r['국가'])
        if not k or k == 'KOR':
            continue
        a = air[k]
        f, t, tr = int(r['도착편수']), int(r['도착여객_전체']), int(r['도착여객_환승'])
        a['flights'] += f
        a['total'] += t
        a['transit'] += tr
        a['years'][r['연도']] = {'flights': f, 'total': t, 'transit': tr}
    return air


def load_quarantine(iso):
    q = defaultdict(lambda: {'general': [], 'priority': []})
    for fn, key in (('2026Q3_검역관리지역.csv', 'general'),
                    ('2026Q3_중점검역관리지역.csv', 'priority')):
        for r in csv.DictReader(open(os.path.join(D11, fn), encoding='utf-8')):
            k = iso(r['국가(지역)'])
            if not k:
                continue
            q[k][key] = [d for d, v in r.items() if d != '국가(지역)' and v.strip()]
    return q


def load_reports(iso):
    """⑫ 해외유입 신고 국가. PHWR을 전부 읽은 것이 아니라 확보한 호만 읽은 '표본'이다."""
    rep = defaultdict(lambda: {'n': 0, 'diseases': defaultdict(int), 'issues': set()})
    span = [None, None]
    issues = set()
    for r in csv.DictReader(open(os.path.join(D12, '해외유입_신고국가.csv'), encoding='utf-8')):
        wk = (int(r['연도']), int(r['주차']))
        span[0] = wk if span[0] is None or wk < span[0] else span[0]
        span[1] = wk if span[1] is None or wk > span[1] else span[1]
        issues.add(r['출처호'])
        k = iso(r['유입국가'])
        if not k:
            continue
        n = int(r['신고수'])
        rep[k]['n'] += n
        rep[k]['diseases'][r['감염병']] += n
        rep[k]['issues'].add(r['출처호'])
    return rep, span, sorted(issues)


def per_million(n, denom):
    return round(n / denom * 1_000_000, 2) if denom else None


def build():
    m, by_iso, ko2iso = load_map()
    iso, unresolved = make_resolver(ko2iso)
    moj, moj_series, months, moj_unmapped = load_moj(iso)
    air = load_air(iso)
    quar = load_quarantine(iso)
    rep, span, issues = load_reports(iso)
    if unresolved:
        raise SystemExit(f'ISO로 못 푼 이름 {len(unresolved)}: {sorted(unresolved)}')

    keys = (set(moj) | set(air) | set(quar) | set(rep)) - {'KOR'}
    rows = []
    for k in sorted(keys):
        geo = by_iso.get(k)
        a = air.get(k)
        direct = (a['total'] - a['transit']) if a else None
        r = rep.get(k)
        n_rep = r['n'] if r else 0
        q = quar.get(k, {'general': [], 'priority': []})
        row = {
            'iso': k, 'ko': DISPLAY.get(k, geo['ko'] if geo else k),
            'region': geo['region'] if geo else None,
            'c': geo['c'] if geo else None, 'on_map': geo is not None,
            'air_direct': direct, 'air_total': a['total'] if a else None,
            'air_transit': a['transit'] if a else None, 'air_flights': a['flights'] if a else None,
            'air_years': a['years'] if a else None,
            'nat_entries': moj.get(k),
            'q_general': q['general'], 'q_priority': q['priority'],
            'rep_n': n_rep,
            'rep_diseases': sorted(r['diseases'].items(), key=lambda x: -x[1]) if r else [],
            'rep_issues': sorted(r['issues']) if r else [],
            'rate_air': per_million(n_rep, direct) if n_rep else (0.0 if direct else None),
            'rate_nat': per_million(n_rep, moj.get(k)) if n_rep else (0.0 if moj.get(k) else None),
        }
        # 국적 대비 노선: 1보다 훨씬 크면 우리 국민·환승 위주 노선, 훨씬 작으면 경유 입국 위주
        row['nat_over_air'] = (round(row['nat_entries'] / direct, 2)
                               if direct and row['nat_entries'] else None)
        rows.append(row)

    # 검역감염병 15종에 한해 (질병, 국가) 쌍으로 지정 여부를 대조한다
    QN = {norm_dz(d): d for d in QUAR_DISEASES}
    pairs_hit, pairs_miss, n_quar_rep = [], [], 0
    for x in rows:
        desig = {norm_dz(d) for d in x['q_general'] + x['q_priority']}
        x['rep_quar'] = []
        for d, n in x['rep_diseases']:
            dn = norm_dz(d)
            if dn not in QN:
                continue
            n_quar_rep += n
            hit = dn in desig
            x['rep_quar'].append({'disease': d, 'n': n, 'designated': hit})
            (pairs_hit if hit else pairs_miss).append(
                {'iso': x['iso'], 'ko': x['ko'], 'disease': d, 'n': n})
    pairs_miss.sort(key=lambda p: -p['n'])

    # 발견 — 계산으로 나오는 것만 적는다
    designated = [x for x in rows if x['q_general'] or x['q_priority']]
    reported = [x for x in rows if x['rep_n']]
    rep_undesignated = sorted([x for x in reported if not (x['q_general'] or x['q_priority'])],
                              key=lambda x: -x['rep_n'])
    desig_no_flight = [x for x in designated if x['air_direct'] is None]
    desig_low_entries = sorted([x for x in designated if (x['nat_entries'] or 0) < 1000],
                               key=lambda x: x['nat_entries'] or 0)
    by_count = sorted([x for x in reported if x['rate_air'] is not None], key=lambda x: -x['rep_n'])
    by_rate = sorted(by_count, key=lambda x: -x['rate_air'])
    rank_count = {x['iso']: i + 1 for i, x in enumerate(by_count)}
    rank_rate = {x['iso']: i + 1 for i, x in enumerate(by_rate)}
    flips = sorted([{'iso': x['iso'], 'ko': x['ko'], 'n': x['rep_n'], 'direct': x['air_direct'],
                     'rate': x['rate_air'], 'rank_count': rank_count[x['iso']],
                     'rank_rate': rank_rate[x['iso']]} for x in by_count],
                   key=lambda x: x['rank_count'] - x['rank_rate'], reverse=True)
    skew = sorted([x for x in rows if x['nat_over_air'] and (x['nat_entries'] or 0) > 20000],
                  key=lambda x: x['nat_over_air'])

    # 위험도 구간: 0이 아닌 값의 사분위
    rates = sorted(x['rate_air'] for x in rows if x['rate_air'])
    def qtl(p):
        return rates[min(len(rates) - 1, int(p * len(rates)))] if rates else 0
    bins = [round(qtl(.25), 2), round(qtl(.5), 2), round(qtl(.75), 2)]

    data = {
        'meta': {
            'period': PERIOD, 'report_span': span, 'report_issues': issues,
            'report_total': sum(x['rep_n'] for x in rows),
            'quarantine_basis': '2026년 3분기(2026.7.1. 기준)',
            'months': months, 'moj_unmapped_entries': moj_unmapped,
            'counts': {'countries': len(rows), 'on_map': sum(1 for x in rows if x['on_map']),
                       'with_air': sum(1 for x in rows if x['air_direct'] is not None),
                       'with_nat': sum(1 for x in rows if x['nat_entries']),
                       'designated': len(designated), 'priority': sum(1 for x in rows if x['q_priority']),
                       'reported': len(reported)},
            'rate_bins': bins,
        },
        'icn': ICN,
        'rows': rows,
        'series': {k: [v.get(mo, 0) for mo in months] for k, v in moj_series.items() if k in keys},
        'findings': {
            'quar_pairs': {'n_reports': n_quar_rep, 'hit': len(pairs_hit), 'miss': len(pairs_miss),
                           'hit_n': sum(p['n'] for p in pairs_hit),
                           'miss_n': sum(p['n'] for p in pairs_miss), 'miss_list': pairs_miss},
            'rep_undesignated': [{'iso': x['iso'], 'ko': x['ko'], 'n': x['rep_n'],
                                  'diseases': x['rep_diseases'][:3]} for x in rep_undesignated],
            'desig_no_flight': [{'iso': x['iso'], 'ko': x['ko'], 'nat': x['nat_entries'],
                                 'k': len(x['q_general']) + len(x['q_priority'])} for x in desig_no_flight],
            'desig_low_entries': [{'iso': x['iso'], 'ko': x['ko'], 'nat': x['nat_entries'] or 0,
                                   'k': len(x['q_general']) + len(x['q_priority'])} for x in desig_low_entries],
            'flips': flips, 'skew': skew and [{'iso': x['iso'], 'ko': x['ko'], 'nat': x['nat_entries'],
                                                'direct': x['air_direct'], 'ratio': x['nat_over_air']}
                                               for x in skew[:5] + skew[-5:]],
        },
        'map': m,
    }

    # CSV 두 장: 표와 발견을 밖에서도 쓸 수 있게
    with open(os.path.join(D15, '국가별_유입_종합.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ISO3', '국가', '지역', '직항도착여객(환승제외)', '환승여객', '도착편수',
                    '외국인입국자(국적)', '검역관리지역_종수', '중점_종수', '유입신고_건수',
                    '유입신고_질병', '건수_백만직항여객당', '건수_백만입국자당', '국적/노선비'])
        for x in rows:
            w.writerow([x['iso'], x['ko'], x['region'], x['air_direct'], x['air_transit'],
                        x['air_flights'], x['nat_entries'], len(x['q_general']), len(x['q_priority']),
                        x['rep_n'], '; '.join(f'{d}({n})' for d, n in x['rep_diseases']),
                        x['rate_air'], x['rate_nat'], x['nat_over_air']])

    # 다른 축(⑯ 검역 정책 실험)이 같은 숫자를 쓰도록 결합 결과를 따로 남긴다
    slim = {'meta': data['meta'], 'quar_diseases': sorted(QUAR_DISEASES),
            'rows': [{k: v for k, v in x.items() if k not in ('c', 'air_years')} for x in rows]}
    json.dump(slim, open(os.path.join(D15, '유입_종합.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))

    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'inflow.template.html'),
                encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    c = data['meta']['counts']
    print(f"→ portal/inflow/index.html  {os.path.getsize(OUT):,}B")
    print(f"  나라 {c['countries']} (지도 {c['on_map']}) · 직항 {c['with_air']} · 국적 {c['with_nat']} · "
          f"검역지정 {c['designated']} (중점 {c['priority']}) · 유입신고 {c['reported']}")
    print(f"  신고 {data['meta']['report_total']}건 / 표본 {len(issues)}호 "
          f"{span[0][0]}-{span[0][1]}주~{span[1][0]}-{span[1][1]}주 · 국적 미매칭 입국자 {moj_unmapped:,}")
    print(f"  발견: 미지정 유입국 {len(rep_undesignated)} · 지정-직항없음 {len(desig_no_flight)} · "
          f"지정-입국<1천 {len(desig_low_entries)} · 위험도 구간 {bins}")
    return data


if __name__ == '__main__':
    build()
