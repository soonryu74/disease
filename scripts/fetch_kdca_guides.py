#!/usr/bin/env python3
"""② 지침 목록 — 질병관리청 누리집 지침 게시판(kdca.go.kr/bbs/kdca/55) 전량 수집 + 감염병포털 목록과 통합

감염병포털(dportal) 게시판만 긁은 358건에는 2023년 이후 신판이 많이 빠져 있었다.
예: 수인성·식품매개감염병 관리지침은 포털에 2022년판까지만 있고, 2023년에 제정된
「바이러스 간염 관리지침(A형·B형·C형·E형)」은 아예 없다. 현행 지침은 누리집 게시판이 정본이다.

산출
  02_지침_정리/data/지침_전체목록_KDCA게시판.csv   누리집 게시판 전량
  02_지침_정리/data/지침_통합목록.csv              포털 + 누리집, 제목·연도로 중복 제거, 출처 표기
"""
import csv
import html
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D02 = os.path.join(ROOT, '02_지침_정리', 'data')
PORTAL = os.path.join(D02, '지침_전체목록_감염병포털.csv')
OUT_KDCA = os.path.join(D02, '지침_전체목록_KDCA게시판.csv')
OUT_ALL = os.path.join(D02, '지침_통합목록.csv')
LIST = 'https://www.kdca.go.kr/bbs/kdca/{board}/artclList.do?page={page}'
VIEW = 'https://www.kdca.go.kr/bbs/kdca/{board}/{id}/artclView.do'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

# 질병관리청 누리집에서 지침·서식·교육자료가 흩어져 있는 게시판.
# 지침 게시판(55) 하나만 보면 코로나19 치료제 안내서·역학조사 서식·검역 개정 공고를 놓친다.
BOARDS = [
    ('55', '지침', 'https://www.kdca.go.kr/kdca/2861/subview.do'),
    ('245', '코로나19지침', 'https://www.kdca.go.kr/kdca/2862/subview.do'),
    ('57', '서식', 'https://www.kdca.go.kr/kdca/2863/subview.do'),
    ('49', '교육자료', 'https://www.kdca.go.kr/kdca/2857/subview.do'),
    ('50', '공지사항', 'https://www.kdca.go.kr/kdca/2769/subview.do'),
]
# 공지사항은 채용·회의록이 대부분이라 지침·감염병 관련만 걸러 담는다.
NOTICE_KEEP = re.compile(r'지침|안내서|매뉴얼|가이드|검역관리지역|감염병|예방접종|역학조사|신고기준|관리기준|표준')


def get(url, tries=6):
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '-m', '60', '-A', UA, url], capture_output=True, text=True)
        if p.stdout and len(p.stdout) > 3000:
            return p.stdout
        time.sleep(2 + i * 2)
    return ''


def parse(h, board):
    out = []
    for block in re.split(r'<tr', h):
        m = re.search(r"jf_viewArtcl\('kdca',\s*'%s',\s*'(\d+)'\)[^>]*>(.*?)</a>" % board, block, re.S)
        if not m:
            continue
        d = re.search(r'\d{4}\.\d{2}\.\d{2}', block)
        t = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
        t = re.sub(r'\s*새글\s*$', '', t)
        out.append({'artclId': m.group(1), '제목': t, '등록일': d.group(0) if d else ''})
    return out


def crawl(board, label, max_pages=400):
    """쪽을 여섯씩 동시에 받는다. 망이 느려 한 쪽씩 받으면 게시판 하나에 30분을 넘긴다."""
    from concurrent.futures import ThreadPoolExecutor
    seen, rows = set(), []
    start, batch = 1, 24
    while start < max_pages:
        pages = list(range(start, start + batch))
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(lambda p: (p, parse(get(LIST.format(board=board, page=p)), board)), pages))
        got_new = False
        for page, rs in sorted(results):
            new = [r for r in rs if r['artclId'] not in seen]
            for r in new:
                seen.add(r['artclId'])
                r['URL'] = VIEW.format(board=board, id=r['artclId'])
                r['게시판'] = label
                rows.append(r)
            if new:
                got_new = True
        print(f'  {label}(#{board}) {start}~{start + batch - 1}쪽 → 누계 {len(rows)}', flush=True)
        if not got_new:
            break
        start += batch
    return rows


def key(title):
    """같은 지침의 판을 묶는 열쇠: 연도·판·꾸밈말을 뺀 제목"""
    t = re.sub(r'\(.*?\)|「|」|\[.*?\]', ' ', title)
    t = re.sub(r'(19|20)\d{2}\s*년도?|제\s*\d+\s*판|\d+차\s*개정판?|개정판?|재안내|안내|배포용|_?전자용|제정', ' ', t)
    return re.sub(r'[\s·‧,.\-_및]', '', t)


def year_of(title, date):
    m = re.search(r'(20\d{2}|19\d{2})', title)
    return int(m.group(1)) if m else (int(date[:4]) if date[:4].isdigit() else 0)


def main():
    print('누리집 게시판 수집 —', ', '.join(f'{l}(#{b})' for b, l, _ in BOARDS))
    kd = []
    for board, label, _ in BOARDS:
        rows_ = crawl(board, label)
        if label == '공지사항':
            before = len(rows_)
            rows_ = [r for r in rows_ if NOTICE_KEEP.search(r['제목'])]
            print(f'    공지사항 {before} → 지침·감염병 관련 {len(rows_)}건만 보관', flush=True)
        kd += rows_
    if len(kd) < 500:
        sys.exit(f'수집이 너무 적다({len(kd)}건). 게시판 구조가 바뀌었거나 망이 막혔다. 기존 파일을 지우지 않는다.')
    kd.sort(key=lambda r: r['등록일'], reverse=True)
    with open(OUT_KDCA, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['게시판', 'artclId', '제목', '등록일', 'URL'])
        w.writeheader()
        w.writerows(kd)
    by = {}
    for r in kd:
        by[r['게시판']] = by.get(r['게시판'], 0) + 1
    print(f'  → {os.path.relpath(OUT_KDCA, ROOT)} {len(kd)}건  ' + ' · '.join(f'{k} {v}' for k, v in by.items()))

    portal = list(csv.DictReader(open(PORTAL, encoding='utf-8-sig')))
    merged = {}
    for src, rows_ in (('KDCA게시판', kd), ('감염병포털', portal)):
        for r in rows_:
            k = (key(r['제목']), year_of(r['제목'], r['등록일']))
            if k in merged:
                merged[k]['출처'] += '+' + src if src not in merged[k]['출처'] else ''
                merged[k].setdefault('URL2', r['URL'])
                continue
            merged[k] = {'제목': r['제목'], '등록일': r['등록일'], 'URL': r['URL'], '출처': src,
                         '게시판': r.get('게시판', ''), '계열키': k[0], '연도': k[1]}
    allrows = sorted(merged.values(), key=lambda r: (r['연도'], r['등록일']), reverse=True)
    # 계열별 판 수·최신 여부
    by_series = {}
    for r in allrows:
        by_series.setdefault(r['계열키'], []).append(r)
    for k, rs in by_series.items():
        rs.sort(key=lambda r: (r['연도'], r['등록일']), reverse=True)
        for i, r in enumerate(rs):
            r['최신판'] = 'Y' if i == 0 else ''
            r['판수'] = len(rs)
    with open(OUT_ALL, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['제목', '등록일', '연도', '출처', '게시판', '최신판', '판수', 'URL', 'URL2', '계열키'])
        w.writeheader()
        w.writerows(allrows)
    only_kd = sum(1 for r in allrows if r['출처'] == 'KDCA게시판')
    only_po = sum(1 for r in allrows if r['출처'] == '감염병포털')
    print(f'  → {os.path.relpath(OUT_ALL, ROOT)} {len(allrows)}건 '
          f'(누리집만 {only_kd} · 포털만 {only_po} · 둘 다 {len(allrows) - only_kd - only_po})')


if __name__ == '__main__':
    main()
