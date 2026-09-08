#!/usr/bin/env python3
"""② 지침 서가 — 질병관리청 지침 2,347건을 '계열'로 접어서 보여주는 쪽

여태 이 자료는 GitHub의 CSV 파일로만 열렸다. 2,347줄짜리 표는 사람이 볼 물건이 아니다.
지침은 대개 해마다 다시 낸다. 그래서 목록이 아니라 **계열**이 단위다 —
「말라리아 관리지침」은 24판이 한 줄이어야 하고, 그 줄을 펴면 1998년부터 2026년까지가 나온다.

산출: portal/guides/index.html  (자체 포함, 자료는 본문에 박아 넣는다)
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_guideline_index import DOC_DROP, doc_kind  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '02_지침_정리', 'data', '지침_통합목록.csv')
TPL = os.path.join(ROOT, 'scripts', 'templates', 'guides.template.html')
OUT = os.path.join(ROOT, 'portal', 'guides', 'index.html')
THIS_YEAR = 2026

# 주소를 그대로 실으면 자료가 세 배로 불어난다. 게시판 글은 규칙이 뻔하므로 부호로 접는다.
RE_KDCA = re.compile(r'^https://www\.kdca\.go\.kr/bbs/kdca/(\d+)/(\d+)/artclView\.do$')
RE_PORT = re.compile(r'^https://dportal\.kdca\.go\.kr/pot/bbs/BD_selectBbs\.do\?q_bbsSn=1001&q_bbsDocNo=(\w+)&q_clsfNo=0$')


def pack_url(u):
    m = RE_KDCA.match(u)
    if m:
        return f'k{m.group(1)}:{m.group(2)}'
    m = RE_PORT.match(u)
    if m:
        return f'p:{m.group(1)}'
    return u


def title_of_series(rows):
    """계열 이름 — 최신판 제목에서 연도·판 표시를 걷어낸 것.
    '2026년도 말라리아 관리지침' → '말라리아 관리지침'"""
    t = rows[0]['제목']
    t = re.sub(r'^\s*[\[【(]?\s*(19|20)\d{2}\s*년?도?\s*[\]】)]?\s*', '', t)
    t = re.sub(r'\s*\(?제?\s*\d+\s*판\)?\s*$|\s*\(\d+차\s*개정\)\s*$', '', t)
    return t.strip() or rows[0]['제목']


def build():
    rows = list(csv.DictReader(open(SRC, encoding='utf-8-sig')))
    ser = defaultdict(list)
    for r in rows:
        ser[r['계열키']].append(r)

    out = []
    for k, rs in ser.items():
        rs.sort(key=lambda r: (int(r['연도']), r['등록일']), reverse=True)
        top = rs[0]
        kind = doc_kind(top['제목'])
        if kind == '기타' and DOC_DROP.search(top['제목']):
            kind = '공고'          # 공모전·채용·입찰. 지우지 않고 갈래로 밀어 둔다
        years = sorted({int(r['연도']) for r in rs})
        out.append({
            'n': title_of_series(rs),
            'y': int(top['연도']),
            'y0': years[0],
            'c': len(rs),
            'b': top['게시판'] or '감염병포털',
            'k': kind,
            'f': top['분야'],
            'e': [[r['제목'], r['등록일'].replace('.', ''), int(r['연도']), pack_url(r['URL'])] for r in rs],
        })
    # 최신판이 새 것부터. 같은 해면 판이 많은 것 — 오래 이어 온 지침이 대개 더 중요하다.
    out.sort(key=lambda s: (-s['y'], -s['c'], s['n']))

    kinds = defaultdict(int)
    boards = defaultdict(int)
    for s in out:
        kinds[s['k']] += 1
        boards[s['b']] += 1
    cur = sum(1 for s in out if s['y'] >= THIS_YEAR - 1)

    data = {
        'meta': {
            'as_of': '2026-09',
            'docs': len(rows), 'series': len(out), 'current': cur,
            'y0': min(s['y0'] for s in out), 'y1': max(s['y'] for s in out),
            'boards': dict(sorted(boards.items(), key=lambda kv: -kv[1])),
            'kinds': dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
        },
        'series': out,
    }
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = open(TPL, encoding='utf-8').read().replace('__DATA__', js)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'지침 서가 — 문서 {len(rows):,}건 → 계열 {len(out):,}개 '
          f'(현행 {cur:,} · {data["meta"]["y0"]}~{data["meta"]["y1"]})')
    print('  갈래 ' + ' · '.join(f'{k} {v}' for k, v in data['meta']['kinds'].items()))
    print(f'  → {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,}B)')


if __name__ == '__main__':
    build()
