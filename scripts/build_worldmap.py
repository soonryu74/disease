#!/usr/bin/env python3
"""Natural Earth 110m → 간략화한 세계지도 (경위도 그대로)

투영은 브라우저에서 한다(지구본·평면 둘 다 그려야 하니). 여기서는
 - 나라마다 ISO3·한글명·중심점·다각형 고리를 뽑고
 - Douglas-Peucker로 점을 줄이고 (허용오차 0.25°)
 - 작은 섬 고리는 버린다
110m 원본은 다각형이 없는 소국(싱가포르·홍콩·몰디브…)이 많다. 그런 곳은 점으로 둔다.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D15 = os.path.join(ROOT, '15_해외유입_지도', 'data')
SRC = os.path.join(D15, 'raw_ne_110m.geojson')
OUT = os.path.join(D15, '세계지도.json')

TOL = 0.25       # 간략화 허용오차(도)
MIN_AREA = 0.6   # 이보다 작은 고리(도²)는 버린다
REGION_KO = {'Asia': '아시아', 'Europe': '유럽', 'Africa': '아프리카',
             'Americas': '아메리카', 'Oceania': '오세아니아', 'Antarctica': '남극'}

# 110m에 다각형이 없는 나라·지역. 국제공항 좌표(경도, 위도)와 UN 지역.
POINTS = {
    'SGP': ('싱가포르', 103.99, 1.36, '아시아'), 'HKG': ('홍콩', 113.91, 22.31, '아시아'),
    'MAC': ('마카오', 113.59, 22.15, '아시아'), 'MDV': ('몰디브', 73.53, 4.19, '아시아'),
    'BHR': ('바레인', 50.63, 26.27, '아시아'), 'MLT': ('몰타', 14.48, 35.86, '유럽'),
    'MUS': ('모리셔스', 57.68, -20.43, '아프리카'), 'SYC': ('세이셸', 55.52, -4.67, '아프리카'),
    'CPV': ('카보베르데', -23.48, 14.95, '아프리카'), 'COM': ('코모로', 43.27, -11.53, '아프리카'),
    'STP': ('상투메프린시페', 6.71, 0.38, '아프리카'), 'GUM': ('괌', 144.80, 13.48, '오세아니아'),
    'MNP': ('사이판', 145.73, 15.12, '오세아니아'), 'PLW': ('팔라우', 134.54, 7.37, '오세아니아'),
    'FSM': ('미크로네시아', 158.21, 6.98, '오세아니아'), 'MHL': ('마셜제도', 171.27, 7.06, '오세아니아'),
    'PYF': ('프랑스령폴리네시아', -149.61, -17.56, '오세아니아'), 'TON': ('통가', -175.15, -21.24, '오세아니아'),
    'WSM': ('사모아', -172.01, -13.83, '오세아니아'), 'NRU': ('나우루', 166.92, -0.55, '오세아니아'),
    'TUV': ('투발루', 179.20, -8.53, '오세아니아'), 'KIR': ('키리바시', 173.15, 1.38, '오세아니아'),
    'COK': ('쿡제도', -159.79, -21.20, '오세아니아'), 'AND': ('안도라', 1.52, 42.51, '유럽'),
    'MCO': ('모나코', 7.42, 43.73, '유럽'), 'LIE': ('리히텐슈타인', 9.52, 47.14, '유럽'),
    'SMR': ('산마리노', 12.46, 43.94, '유럽'), 'VAT': ('교황청', 12.45, 41.90, '유럽'),
    'BRB': ('바베이도스', -59.49, 13.07, '아메리카'), 'GRD': ('그레나다', -61.79, 12.00, '아메리카'),
    'DMA': ('도미니카연방', -61.30, 15.55, '아메리카'), 'LCA': ('세인트루시아', -60.95, 13.73, '아메리카'),
    'VCT': ('세인트빈센트그레나딘', -61.21, 13.14, '아메리카'), 'KNA': ('세인트키츠네비스', -62.72, 17.31, '아메리카'),
    'ATG': ('앤티가바부다', -61.79, 17.14, '아메리카'), 'GUF': ('프랑스령기아나', -52.36, 4.82, '아메리카'),
    'GLP': ('과들루프', -61.53, 16.27, '아메리카'), 'MTQ': ('마르티니크', -61.00, 14.59, '아메리카'),
    'REU': ('레위니옹', 55.51, -20.89, '아프리카'), 'MYT': ('마요트', 45.28, -12.80, '아프리카'),
    'ABW': ('아루바', -70.02, 12.50, '아메리카'), 'SXM': ('신트마르턴', -63.11, 18.04, '아메리카'),
    'MAF': ('세인트마틴', -63.05, 18.10, '아메리카'), 'BLM': ('생바르텔르미', -62.84, 17.90, '아메리카'),
    'AIA': ('앵귈라', -63.06, 18.20, '아메리카'), 'VGB': ('영국령버진아일랜드', -64.54, 18.44, '아메리카'),
    'VIR': ('미국령버진아일랜드', -64.97, 18.34, '아메리카'), 'TCA': ('터크스케이커스', -71.14, 21.77, '아메리카'),
    'TKL': ('토켈라우', -171.85, -9.20, '오세아니아'), 'WLF': ('왈리스푸투나', -176.20, -13.24, '오세아니아'),
    'NFK': ('노퍽섬', 167.94, -29.04, '오세아니아'), 'IOT': ('영국령인도양지역', 72.41, -7.31, '아시아'),
}


def ring_area(r):
    a = 0.0
    for i in range(len(r) - 1):
        a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return abs(a) / 2


def dp(pts, tol):
    """Douglas-Peucker."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    # 첫·끝점이 같으면 기준선이 점으로 무너진다. 첫점에서 가장 먼 점을 먼저 고정한다.
    far = max(range(1, len(pts) - 1),
              key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    keep[far] = True
    stack = [(0, far), (far, len(pts) - 1)]
    while stack:
        s, e = stack.pop()
        if e <= s + 1:
            continue
        ax, ay = pts[s]
        bx, by = pts[e]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1e-12
        best, bi = 0.0, -1
        for i in range(s + 1, e):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(s, bi), (bi, e)]
    return [p for p, k in zip(pts, keep) if k]


def centroid(r):
    a = cx = cy = 0.0
    for i in range(len(r) - 1):
        f = r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
        a += f
        cx += (r[i][0] + r[i + 1][0]) * f
        cy += (r[i][1] + r[i + 1][1]) * f
    if abs(a) < 1e-9:
        return r[0]
    return [cx / (3 * a), cy / (3 * a)]


def build():
    g = json.load(open(SRC, encoding='utf-8'))
    out, small, n_pts_in, n_pts_out = [], [], 0, 0
    for f in g['features']:
        p = f['properties']
        iso = p.get('ISO_A3')
        if not iso or iso == '-99':
            iso = p.get('ADM0_ISO') or p.get('ADM0_A3')
        geom = f['geometry']
        polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        rings, biggest, big_area = [], None, -1
        for poly in polys:
            outer = poly[0]  # 구멍은 110m에서 무시해도 된다
            n_pts_in += len(outer)
            a = ring_area(outer)
            if a > big_area:
                big_area, biggest = a, outer
            if a < MIN_AREA:
                continue
            simp = dp(outer, TOL)
            if len(simp) < 4:
                continue
            simp = [[round(x, 2), round(y, 2)] for x, y in simp]
            n_pts_out += len(simp)
            rings.append(simp)
        c = centroid(biggest)
        rec = {'iso': iso, 'ko': p.get('NAME_KO') or p['NAME'], 'name': p['NAME'],
               'region': REGION_KO.get(p.get('REGION_UN'), p.get('REGION_UN')),
               'c': [round(c[0], 2), round(c[1], 2)]}
        if rings:
            out.append(dict(rec, rings=rings))
        else:
            small.append(rec)  # 룩셈부르크·바누아투처럼 고리가 다 작은 나라는 점으로
    have = {c['iso'] for c in out}
    pts = small + [{'iso': k, 'ko': v[0], 'region': v[3], 'c': [v[1], v[2]]}
                   for k, v in POINTS.items() if k not in have]
    data = {'source': 'Natural Earth 110m admin-0 (public domain)', 'tolerance_deg': TOL,
            'min_ring_area_deg2': MIN_AREA, 'countries': out, 'points': pts}
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'→ {os.path.relpath(OUT, ROOT)}  {os.path.getsize(OUT):,}B')
    print(f'  다각형 {len(out)}개국 · 점 {len(pts)}곳 · 꼭짓점 {n_pts_in:,} → {n_pts_out:,}')


if __name__ == '__main__':
    build()
