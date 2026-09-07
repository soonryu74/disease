#!/usr/bin/env python3
"""질병관리청「중점검역관리지역 및 검역관리지역 안내」PDF → 구조화 JSON.

검역법 제5조에 따라 질병관리청장이 검역전문위원회 심의를 거쳐 지정하는
검역관리지역·중점검역관리지역의 '국가(지역) × 검역감염병' 매트릭스를 복원한다.

## 복원 방법과 검산
원문 표는 국가 행 × 감염병 열에 ●를 찍은 형태다. PDF 텍스트에서는 열 머리글이
세로로 쪼개져 이름과 열 위치를 직접 잇기 어렵다. 그래서:

 1. 머리글에서 '감염병명(국가수)'를 **왼쪽→오른쪽 순서대로** 읽는다.
 2. 표 본문의 ● x좌표를 군집화해 열을 만든다.
 3. 열을 순서대로 감염병에 대응시킨다.
 4. **검산**: 각 열의 ● 개수가 머리글이 공표한 국가 수와 모두 일치해야 한다.
    하나라도 어긋나면 매트릭스를 채택하지 않고 `verified: false`로 표시한다.

검산을 통과하지 못한 매트릭스는 내보내지 않는다. 추정하지 않는다.

사용:
    python3 scripts/parse_quarantine.py <pdf...> [--json out.json]
"""
import json
import re
import sys

from pypdf import PdfReader

DOT = '●'
CANON = ['동물인플루엔자인체감염증', '에볼라바이러스병', '중동호흡기증후군', '페스트', '콜레라',
         '황열', '마버그열', '라싸열', '크리미안콩고출혈열', '폴리오', '홍역', '뎅기열',
         '치쿤구니야열', '지카바이러스감염증', '니파바이러스감염증', '엠폭스',
         '남아메리카출혈열', '리프트밸리열', '두창', '중증급성호흡기증후군', '신종인플루엔자']


def norm(s):
    return re.sub(r'[\s･· ]+', '', s or '')


def layout_pages(path):
    r = PdfReader(path)
    return [(p.extract_text(extraction_mode='layout') or '') for p in r.pages]


LABELS = {'구분', '국가', '또는', '지역', '대상', '개'}


def match_canon(raw):
    """열 머리글에서 이어붙인 조각 → 정식 검역감염병명.

    '지카감염증'처럼 중간 조각('바이러스')이 옆 열과 뭉쳐 빠질 수 있으므로
    공통 접두 길이가 가장 긴 병명을 고르고, 동점이면 채택하지 않는다.
    """
    raw = re.sub(r'\(\d{1,3}\)', '', raw)
    if not raw:
        return None
    scored = []
    for c in CANON:
        n = 0
        while n < min(len(c), len(raw)) and c[n] == raw[n]:
            n += 1
        if n >= 2:
            scored.append((n, c))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def header_diseases(lines, tol=2):
    """머리글 줄들 → [(감염병, 공표국가수)] 왼쪽→오른쪽 순.

    이름이 세로로 쪼개지므로 조각의 x좌표를 tol 이내로 군집한 뒤 줄 순서대로 잇는다.
    """
    frags = []
    for li, ln in enumerate(lines):
        for m in re.finditer(r'[가-힣A-Za-z]+|\(\d{1,3}\)', ln):
            t = m.group(0)
            if t in LABELS:
                continue
            frags.append([m.start(), li, t])
    if not frags:
        return []
    frags.sort(key=lambda f: (f[0], f[1]))
    # 군집 기준은 '직전 조각'이 아니라 '군집 시작점' — 열 간격(4~5)보다 작은 tol로
    # 연쇄 병합(라싸열→크리미안→폴리오가 한 덩어리가 되는 현상)을 막는다.
    groups, cur = [], [frags[0]]
    for f in frags[1:]:
        if f[0] - cur[0][0] <= tol:
            cur.append(f)
        else:
            groups.append(cur)
            cur = [f]
    groups.append(cur)

    out = []
    for g in groups:
        g.sort(key=lambda f: f[1])
        raw = ''.join(t for _, _, t in g)
        cnt = None
        cm = re.search(r'\((\d{1,3})\)', raw)
        if cm:
            cnt = int(cm.group(1))
        name = match_canon(raw)
        if name:
            out.append((min(x for x, _, _ in g), name, cnt))
    out.sort()
    # 같은 병명이 인접 군집에 중복되면 왼쪽만 남긴다
    # 개수를 못 붙인 열에는 아직 아무도 쓰지 않은 '(n)' 토큰 중 가장 가까운 것을 붙인다
    used = {c for _, _, c in out if c is not None}
    nums = []
    for li, ln in enumerate(lines):
        for m in re.finditer(r'\((\d{1,3})\)', ln):
            nums.append((m.start(), int(m.group(1))))
    out2 = []
    for x, n, c in out:
        if c is None:
            cand = sorted(((abs(nx - x), nx, nv) for nx, nv in nums if abs(nx - x) <= 8),
                          key=lambda t: t[0])
            for _d, nx, nv in cand:
                if (nx, nv) not in used:
                    c = nv
                    used.add((nx, nv))
                    break
        out2.append((x, n, c))
    out = out2

    best_of = {}
    for x, n, c in out:
        prev = best_of.get(n)
        if prev is None or (prev[1] is None and c is not None):
            best_of[n] = (x, c)
    return [(n, c, x) for n, (x, c) in sorted(best_of.items(), key=lambda kv: kv[1][0])]


def header_diseases_best(lines):
    """열 간격은 표마다 달라 허용오차를 하나로 고정할 수 없다.
    여러 오차로 읽어 '공표 국가수를 가장 많이 회수한' 결과를 채택한다."""
    best, best_score = [], (-1, 1, -1)
    for tol in (1, 2, 3, 4, 5):
        ds = header_diseases(lines, tol)
        with_c = sum(1 for _, c, _x in ds if c is not None)
        without = len(ds) - with_c
        score = (with_c, -without, len(ds))
        if score > best_score:
            best, best_score = ds, score
    return best


def page_header_blocks(lines):
    """한 쪽에서 매트릭스 머리글 후보 블록들(줄 리스트)을 반환한다."""
    out = []
    for i, ln in enumerate(lines):
        f = norm(ln)
        if DOT in ln:
            continue
        if '국가' in f and ('지역' in f or '구분' in f):
            for back, fwd in ((1, 4), (2, 5), (0, 4), (0, 3), (1, 3), (2, 6), (3, 7), (0, 6), (1, 6), (2, 7), (3, 5), (0, 5)):
                out.append(lines[max(0, i - back):i + fwd])
    return out


def page_rows(lines):
    """한 쪽의 표 본문 행 → [(국가, [● x좌표...])]

    두 가지 원문 특성을 처리한다.
      1) 국가명이 두 줄로 나뉜다(예: '콩고민주' + '공화국') → 이어 붙인다.
      2) 행 높이가 커서 ●가 국가명 없는 줄에 찍힌다(예: 중국) → 인접 국가에 붙이되,
         직전 국가가 그 열에 이미 ●를 가졌으면 다음 국가의 것으로 본다.
    """
    ROW = r'^\s*(?:[가-힣()\s\d개･·・]{0,16}?)(\d{1,3})\s+([가-힣A-Za-z][가-힣A-Za-z\s()]*?)\s{2,}'
    # 원문에서 국가명 뒤쪽만 남는 조각들 — 앞줄 끝의 낱말과 이어 붙여야 한다
    SUFFIX_ONLY = {'공화국', '자치구', '제도', '연방', '그레나딘', '바부다', '네비스',
                   '아일랜드', '토바고', '케이커스', '헤르체고비나', '푸투나'}
    REGION_WORDS = {'아시아', '중동', '아프리카', '미주', '오세아니아', '유럽', '구분'}
    rows, pending, consumed = [], [], set()   # pending: 아직 주인을 못 정한 ● x 목록
    for li, ln in enumerate(lines):
        if li in consumed:
            continue
        m = re.match(ROW, ln)
        country = None
        if m:
            c = norm(m.group(2))
            if c and len(c) <= 22:
                country = c
        dots = [mm.start() for mm in re.finditer(DOT, ln)]

        if country in SUFFIX_ONLY and li > 0:
            # 예: ' 미주･        도미니카' / '오세아니아  8  공화국   ●'
            prev = [w for w in re.findall(r'[가-힣]{2,12}', lines[li - 1])
                    if w not in REGION_WORDS and w not in SUFFIX_ONLY]
            if prev:
                country = prev[-1] + country

        if country is not None:
            # 다음 줄이 ●도 번호도 없는 짧은 한글이면 이어지는 국가명으로 본다
            nxt = lines[li + 1] if li + 1 < len(lines) else ''
            if (DOT not in nxt and not re.match(ROW, nxt)
                    and re.match(r'^\s*[가-힣]{2,10}\s*$', nxt)):
                country += norm(nxt)
                consumed.add(li + 1)   # 이 줄은 이름 조각으로 이미 썼다
            rows.append([country, list(dots)])
            # 앞서 주인을 못 정한 ●는 직전 국가가 이미 그 열을 가졌으면 이 국가 것으로
            for x in pending:
                if rows and len(rows) >= 2 and x in rows[-2][1]:
                    rows[-1][1].append(x)
                elif len(rows) >= 2:
                    rows[-2][1].append(x)
                else:
                    rows[-1][1].append(x)
            pending = []
        else:
            # 국가명이 두 줄로 나뉘고 ●가 둘째 줄에 찍힌 경우
            # (예: '8  도미니카' / '   공화국   ● ●') → 직전 행에 이름과 ●를 함께 붙인다
            cont = re.match(r'^\s{2,}([가-힣]{2,10})(?:\s|$)', ln)
            if cont and rows and not re.search(r'\d', ln.split(DOT)[0]):
                rows[-1][0] += norm(cont.group(1))
                rows[-1][1].extend(dots)
            elif dots:
                pending.extend(dots)
    for x in pending:
        if rows:
            rows[-1][1].append(x)
    return [(c, xs) for c, xs in rows if xs]


def assign_page(rows, cols, tol, off):
    """(국가→감염병집합, 열별 개수, 미배정수) — ●는 열 머리글 x에 최근접 배정."""
    mtx, counts, unassigned = {}, {d: 0 for d, _, _ in cols}, 0
    for country, xs in rows:
        for x in xs:
            d, _n, hx = min(cols, key=lambda c: abs(c[2] - (x - off)))
            if abs(hx - (x - off)) <= tol:
                mtx.setdefault(country, set()).add(d)
                counts[d] += 1
            else:
                unassigned += 1
    return mtx, counts, unassigned


def build_matrix(pages):
    """쪽마다 머리글 x가 달라 열 위치를 쪽 단위로 잡고, 전체 합계를 공표 국가수와 검산한다."""
    declared, per_page = None, []
    for pg in pages:
        lines = pg.split('\n')
        rows = page_rows(lines)
        if not rows:
            continue
        dots = sorted({x for _c, xs in rows for x in xs})
        best = None
        for blk in page_header_blocks(lines):
            cols = header_diseases_best(blk)
            if len(cols) < 2 or any(n is None for _, n, _ in cols):
                continue
            hx = [c[2] for c in cols]
            # 정렬 오프셋: ● x 집합이 열 x 집합에 가장 잘 겹치는 이동량
            aligned = None
            for off in range(0, 5):   # ●는 열 이름보다 살짝 오른쪽에 찍힌다
                cost = sum(min(abs(d - off - h) for h in hx) for d in dots)
                key = (cost, abs(off))
                if aligned is None or key < aligned[0]:
                    aligned = (key, off)
            off = aligned[1]
            resid = max((min(abs(d - off - h) for h in hx) for d in dots), default=0)
            tol = max(2, min(resid, 4))
            mtx, counts, unass = assign_page(rows, cols, tol, off)
            score = (-unass, -aligned[0][0], len(cols))
            if best is None or score > best[0]:
                best = (score, cols, mtx, counts, unass)
        if best is None:
            per_page.append(None)
            continue
        per_page.append(best)

    # 절 전체에서 가장 흔한 열 구성을 정본으로 삼고, 다른 쪽은 미파싱 처리
    from collections import Counter
    sigs = Counter(tuple(d for d, _n, _x in b[1]) for b in per_page if b)
    if not sigs:
        return {'verified': False, 'reason': '매트릭스 머리글을 확정하지 못함',
                'pages_with_rows': 0, 'pages_unparsed': len(per_page)}, {}
    canon_sig = max(sigs, key=lambda k: (len(k), sigs[k]))
    fixed = []
    for b in per_page:
        if b and tuple(d for d, _n, _x in b[1]) == canon_sig:
            _, cols, mtx, counts, unass = b
            if declared is None:
                declared = [(d, n) for d, n, _ in cols]
            fixed.append((mtx, counts, unass))
        else:
            fixed.append(None)
    per_page = fixed

    res = {'verified': False,
           'diseases_declared': [{'disease': d, 'countries_declared': n}
                                 for d, n in (declared or [])],
           'pages_with_rows': len([p for p in per_page if p is not None]),
           'pages_unparsed': len([p for p in per_page if p is None])}
    if not declared:
        res['reason'] = '매트릭스 머리글을 확정하지 못함'
        return res, {}

    total, counts, unass = {}, {d: 0 for d, _ in declared}, 0
    for p in per_page:
        if p is None:
            continue
        m, c, u = p
        for k, v in m.items():
            total.setdefault(k, set()).update(v)
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
        unass += u
    exp = dict(declared)
    by_dis = {}
    for c, ds in total.items():
        for x in ds:
            by_dis.setdefault(x, set()).add(c)
    mism = {}
    for d in exp:
        got_dots = counts.get(d, 0)
        got_uniq = len(by_dis.get(d, ()))
        if exp[d] != got_dots or exp[d] != got_uniq:
            mism[d] = {'공표': exp[d], '복원_●수': got_dots, '복원_국가수': got_uniq}
    res.update({'columns_found': len(declared), 'unassigned_marks': unass,
                'counts_recovered': counts, 'mismatch': mism,
                'countries_in_matrix': len(total),
                'verified': (not mism and unass == 0 and res['pages_unparsed'] == 0)})
    if mism:
        res['reason'] = '열별 ● 개수가 공표 국가수와 불일치 — 매트릭스 미채택'
    return res, {c: sorted(v) for c, v in total.items()}


def region_lists(pages):
    """'대상 국가(지역)' 권역 요약표 → {권역: {count, countries}} (괄호 안 쉼표 보존)"""
    out = {}
    for pg in pages:
        lines = pg.split('\n')
        for i, ln in enumerate(lines):
            m = re.match(r'^\s*([가-힣][가-힣･·\s]{1,14}?)\s*\(\s*(\d{1,3})\s*개\s*\)\s+(.*)$', ln)
            if not m:
                continue
            label = norm(m.group(1))
            if label in out or DOT in ln:
                continue
            body = m.group(3)
            for nxt in lines[i + 1:i + 5]:
                if re.match(r'^\s*[가-힣][가-힣･·\s]{1,14}?\s*\(\s*\d{1,3}\s*개\s*\)', nxt):
                    break
                if not nxt.strip() or '대상' in nxt or '구분' in nxt or DOT in nxt:
                    break
                body += ' ' + nxt.strip()
            names, depth, cur = [], 0, ''
            for ch in body:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                if ch in ',，' and depth <= 0:
                    names.append(cur)
                    cur = ''
                else:
                    cur += ch
            names.append(cur)
            names = [re.sub(r'\s+', '', n) for n in names if n.strip()]
            if names:
                out[label] = {'count': int(m.group(2)), 'countries': names}
    return out


def parse(path):
    pages = layout_pages(path)
    full = '\n'.join(pages)
    out = {'source_file': path.split('/')[-1], 'pages': len(pages)}

    m = re.search(r'(\d{4})\s*년\s*(\d)\s*분기', full)
    if m:
        out['period'], out['period_kind'] = f'{m.group(1)}-Q{m.group(2)}', 'quarter'
    else:
        m = re.search(r'(\d{4})\s*년도?\s*(상반기|하반기)', full)
        if m:
            out['period'] = f'{m.group(1)}-{"H1" if m.group(2)=="상반기" else "H2"}'
            out['period_kind'] = 'half'
    m = re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*기준', full)
    if m:
        out['as_of'] = f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    out['legal_basis'] = '검역법 제5조(검역관리지역등의 지정)·제2조·제12조의2'
    if re.search(r'1천만원\s*이하의\s*과태료', full):
        out['penalty'] = '1천만원 이하 과태료(검역법)'

    # 절 나누기
    pri, gen, mode = [], [], None
    for pg in pages:
        f = norm(pg)
        if re.search(r'1\.중점검역관리지역', f):
            mode = 'p'
        elif re.search(r'2\.검역관리지역', f):
            mode = 'g'
        if mode == 'p':
            pri.append(pg)
        elif mode == 'g':
            gen.append(pg)

    for key, pgs in (('priority', pri), ('general', gen)):
        if not pgs:
            out[key] = {'verified': False, 'reason': '해당 절을 찾지 못함'}
            continue
        # 머리글 블록: '국가 또는 지역'이 있고 ●가 없는 줄부터 4줄
        meta, mtx = build_matrix(pgs)
        regs = region_lists(pgs)
        by_dis = {}
        if meta.get('verified'):
            for c, ds in mtx.items():
                for d in ds:
                    by_dis.setdefault(d, []).append(c)
        out[key] = dict(meta,
                        regions=regs,
                        country_total=sum(v['count'] for v in regs.values()) or None,
                        diseases_by_country=mtx if meta.get('verified') else {},
                        countries_by_disease={d: sorted(v) for d, v in sorted(by_dis.items())})
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    res = [parse(p) for p in args]
    js = json.dumps(res if len(res) > 1 else res[0], ensure_ascii=False, indent=1)
    if '--json' in sys.argv:
        dst = sys.argv[sys.argv.index('--json') + 1]
        open(dst, 'w', encoding='utf-8').write(js)
        print('→', dst)
    else:
        print(js)
