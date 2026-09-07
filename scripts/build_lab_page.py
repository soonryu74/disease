#!/usr/bin/env python3
"""10_진단검사_감시 CSV → portal/lab/index.html (병원체감시 대시보드).

작은 배수(small multiples)로 병원체별 주간 검출률을 그린다. 각 패널이 단일 계열이므로
계열 색 구분 문제가 없고, 계절성 비교가 목적인 이 자료에 맞는 형태다.
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, '10_진단검사_감시', 'data')
OUT = os.path.join(ROOT, 'portal', 'lab', 'index.html')

RESP = ['아데노', '보카', '파라인플루엔자', 'RSV', '리노', '메타뉴모', '코로나', '인플루엔자', '코로나19']
RESP_FULL = {'아데노': '아데노바이러스', '보카': '보카바이러스', '파라인플루엔자': '파라인플루엔자바이러스',
             'RSV': '호흡기세포융합바이러스(RSV)', '리노': '리노바이러스', '메타뉴모': '메타뉴모바이러스',
             '코로나': '코로나바이러스', '인플루엔자': '인플루엔자바이러스', '코로나19': '코로나19바이러스'}
DIARB = ['살모넬라', '병원성대장균', '세균성이질', '장염비브리오', '비브리오콜레라',
         '캄필로박터', '클로스트리듐퍼프린젠스', '황색포도알균', '바실루스세레우스']
DIARV = ['노로', '그룹A로타', '장내아데노', '아스트로', '사포']
DIARV_FULL = {'노로': '노로바이러스', '그룹A로타': '그룹A 로타바이러스', '장내아데노': '장내 아데노바이러스',
              '아스트로': '아스트로바이러스', '사포': '사포바이러스'}


def rd(name):
    with open(os.path.join(DATA, name), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def series(rows, cols, suffix=''):
    """[{t:'2026-35', y:2026, w:35, v:{병원체:값}}] 시간순"""
    out = []
    for r in sorted(rows, key=lambda r: (int(r['연도']), int(r['주차']))):
        y, w = int(r['연도']), int(r['주차'])
        out.append({'t': f'{y}-{w:02d}', 'y': y, 'w': w,
                    'v': {c: num(r.get(c + suffix)) for c in cols},
                    'tot': num(r.get('합계' + suffix)) if suffix else None,
                    'n': num(r.get('검체수')), 'src': r.get('출처호')})
    return out


def build():
    resp = rd('호흡기바이러스_주간검출률.csv')
    dv = rd('급성설사바이러스_주간검출.csv')
    db = rd('급성설사세균_주간분리.csv')
    flu = rd('인플루엔자_양성률.csv')

    data = {
        'resp': {'cols': RESP, 'full': RESP_FULL,
                 'total': [{'t': f"{int(r['연도'])}-{int(r['주차']):02d}", 'v': num(r['총검출률']),
                            'src': r['출처호']}
                           for r in sorted(resp, key=lambda r: (int(r['연도']), int(r['주차'])))],
                 'rows': series(resp, RESP)},
        'diarv': {'cols': DIARV, 'full': DIARV_FULL, 'rows': series(dv, DIARV, '_검출률'),
                  'unit': '검출률'},
        'diarb': {'cols': DIARB, 'full': {c: c for c in DIARB}, 'rows': series(db, DIARB, '_분리율'),
                  'unit': '분리율'},
        'flu': [{'t': f"{int(r['연도'])}-{int(r['주차']):02d}", 'p': num(r['양성률']),
                 'h1': num(r['A_H1N1pdm09']), 'h3': num(r['A_H3N2']), 'b': num(r['B']),
                 'clinics': num(r['표본의료기관수'])}
                for r in sorted(flu, key=lambda r: (int(r['연도']), int(r['주차'])))],
        'issues': json.load(open(os.path.join(DATA, '수집원장.json'), encoding='utf-8')),
    }
    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'lab.template.html'), encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    print(f'→ portal/lab/index.html  {os.path.getsize(OUT):,}B '
          f'(호흡기 {len(resp)}주 · 설사바이러스 {len(dv)}주 · 설사세균 {len(db)}주)')


if __name__ == '__main__':
    build()
