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


YEAR_MIN, YEAR_MAX = 1995, 2030


def year_of(title, date):
    """제목의 연도를 쓰되, 말이 되는 값일 때만. '220902기준' 같은 날짜 토막이
    2090년으로 읽히던 오류가 있었다. 그런 경우 등록일 연도를 쓴다."""
    reg = int(date[:4]) if date[:4].isdigit() else 0
    for m in re.finditer(r'(19|20)\d{2}', title):
        y = int(m.group(0))
        if YEAR_MIN <= y <= YEAR_MAX:
            return y
    return reg


# 감염병 지침 게시판에는 만성질환·건강증진 사업 지침도 섞여 올라온다(공지·교육자료 게시판 탓).
# 지우지 않고 갈래만 표시해 서가에서 걸러 볼 수 있게 한다.
NON_ID = ('고혈압', '당뇨', '심뇌혈관', '건강증진', '퇴원손상', '금연', '영양조사', '비만',
          '만성질환', '자살', '치매', '구강건강', '희귀질환', '건강검진', '낙상', '손상감시',
          '아토피', '천식', '알레르기', '심폐소생', '응급처치', '모유수유', '노인건강')
ID_HINT = ('감염', '방역', '검역', '결핵', '예방접종', '백신', '역학조사', '병원체', '항생제',
           '내성', '살균', '소독', '매개체', '방제', '격리', '검체', '진단검사', '신고')


def field_of(title):
    if any(k in title for k in ID_HINT):
        return '감염병'
    return '그 밖' if any(k in title for k in NON_ID) else '감염병'


def merge(kd):
    """누리집 수집분 + 감염병포털 목록을 계열키·연도로 합친다.
    수집을 다시 하지 않고 정제 규칙만 고칠 때가 잦아 따로 뺐다(--merge-only)."""
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
                         '게시판': r.get('게시판', ''), '계열키': k[0], '연도': k[1],
                         '분야': field_of(r['제목'])}
    allrows = sorted(merged.values(), key=lambda r: (r['연도'], r['등록일']), reverse=True)
    # 계열별 판 수·최신 여부
    by_series = {}
    for r in allrows:
        by_series.setdefault(r['계열키'], []).append(r)
    for k, rs in by_series.items():
        rs.sort(key=lambda r: (r['연도'], r['등록일']), reverse=True)
        # 계열 안에서 갈래가 갈리면 다수결로 하나로 맞춘다. 같은 지침의 판끼리
        # '감염병'과 '그 밖'으로 나뉘면 서가에서 계열이 두 쪽으로 쪼개 보인다.
        f = '그 밖' if sum(1 for r in rs if r['분야'] == '그 밖') * 2 > len(rs) else '감염병'
        for i, r in enumerate(rs):
            r['최신판'] = 'Y' if i == 0 else ''
            r['판수'] = len(rs)
            r['분야'] = f
    with open(OUT_ALL, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['제목', '등록일', '연도', '분야', '출처', '게시판', '최신판', '판수', 'URL', 'URL2', '계열키'])
        w.writeheader()
        w.writerows(allrows)
    only_kd = sum(1 for r in allrows if r['출처'] == 'KDCA게시판')
    only_po = sum(1 for r in allrows if r['출처'] == '감염병포털')
    other = sum(1 for r in allrows if r['분야'] == '그 밖')
    print(f'  → {os.path.relpath(OUT_ALL, ROOT)} {len(allrows)}건 '
          f'(누리집만 {only_kd} · 포털만 {only_po} · 둘 다 {len(allrows) - only_kd - only_po})')
    print(f'    갈래 — 감염병 {len(allrows) - other} · 그 밖 {other}')
    return allrows


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
    merge(kd)


if __name__ == '__main__':
    if '--merge-only' in sys.argv:
        rows = list(csv.DictReader(open(OUT_KDCA, encoding='utf-8-sig')))
        print(f'수집 건너뜀 — {os.path.relpath(OUT_KDCA, ROOT)} {len(rows)}건을 다시 합친다')
        merge(rows)
    else:
        main()
