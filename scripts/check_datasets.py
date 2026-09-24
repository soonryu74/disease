#!/usr/bin/env python3
"""자료 상시 점검 — 무엇이 어긋났는지 매번 같은 방식으로 본다.

이 저장소는 여러 갈래(도감·연대기·지침·시뮬레이터·검역·연보)에서 같은 감염병을
저마다의 표기로 부른다. 한 곳의 이름이 바뀌면 다른 곳의 연결이 조용히 끊긴다.
사람이 눈으로 훑어서는 못 잡으므로 여기서 기계로 본다.

보는 것
 1) 원장 파일이 비어 있지 않고 읽히는가
 2) 표에 있어야 할 열이 있고, 연도 열의 범위가 말이 되는가
 3) 모듈끼리 부르는 감염병 이름이 서로 닿는가 (별칭사전·표기_원장으로 맞춰 본 뒤)
 4) 포털 각 쪽이 인코딩·언어·제목을 갖추고, 루트절대 경로를 쓰지 않는가
 5) 데이터 센터가 내건 파일이 실제로 있는가

끝에 요약을 찍고, 고쳐야 할 것(ERROR)이 있으면 1을 반환한다.
경고(WARN)는 판단이 필요한 것이라 반환값을 바꾸지 않는다 — 사람이 보고 정한다.
"""
import csv
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

FILES = os.path.join(ROOT, 'portal', 'data', 'files')
PORTAL = os.path.join(ROOT, 'portal')
THIS_YEAR = date.today().year

ERRORS, WARNS, NOTES = [], [], []


def err(where, msg):
    ERRORS.append((where, msg))


def warn(where, msg):
    WARNS.append((where, msg))


def note(msg):
    NOTES.append(msg)


def norm(s):
    """모듈마다 다른 띄어쓰기·괄호·가운뎃점을 지운 대조용 이름."""
    return re.sub(r'[\s()（）·・\-–—/]', '', s or '').lower()


# ── 1. 원장 파일 ─────────────────────────────────────────────────────────
def check_files():
    if not os.path.isdir(FILES):
        err('데이터', f'{FILES} 가 없다')
        return {}, {}
    csvs, jsons = {}, {}
    for f in sorted(os.listdir(FILES)):
        p = os.path.join(FILES, f)
        size = os.path.getsize(p)
        if size == 0:
            err(f, '빈 파일')
            continue
        if f.endswith('.csv'):
            try:
                rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
            except Exception as e:                       # noqa: BLE001
                err(f, f'읽지 못함 — {e}')
                continue
            if not rows:
                err(f, '머리글만 있고 자료가 없다')
                continue
            csvs[f] = rows
        elif f.endswith('.json'):
            try:
                jsons[f] = json.load(open(p, encoding='utf-8'))
            except Exception as e:                       # noqa: BLE001
                err(f, f'JSON을 읽지 못함 — {e}')
    note(f'원장 파일 {len(csvs)}개 표 · {len(jsons)}개 JSON')
    return csvs, jsons


# ── 2. 연도 열 ───────────────────────────────────────────────────────────
YEAR_RE = re.compile(r'^(19|20)\d{2}$')


def check_years(csvs):
    n = 0
    for f, rows in csvs.items():
        cols = [c for c in (rows[0].keys() if rows else []) if c and YEAR_RE.match(c.strip())]
        if not cols:
            continue
        n += 1
        ys = sorted(int(c) for c in cols)
        if ys[-1] > THIS_YEAR:
            err(f, f'아직 오지 않은 연도 열이 있다 — {ys[-1]}')
        if ys[-1] < THIS_YEAR - 2:
            warn(f, f'마지막 연도가 {ys[-1]} — {THIS_YEAR - ys[-1]}해 묵었다')
        missing = [y for y in range(ys[0], ys[-1] + 1) if y not in ys]
        if missing:
            warn(f, f'연도가 비어 있다 — {missing}')
        # 값이 전부 비어 있는 연도
        for c in cols:
            vals = [r.get(c) for r in rows]
            if all(v in (None, '', '-') for v in vals):
                warn(f, f'{c}년 열이 통째로 비어 있다')
    note(f'연도 계열 표 {n}개 확인')


# ── 3. 모듈끼리 이름이 닿는가 ────────────────────────────────────────────
def alias_map(jsons):
    """별칭사전·표기_원장을 합쳐 '이 이름 → 대표 이름' 대응표를 만든다."""
    m = {}
    d = jsons.get('별칭사전.json') or {}
    for e in d.get('entries', []):
        c = e.get('canonical')
        if not c:
            continue
        m[norm(c)] = c
        for a in e.get('aliases', []) or []:
            if a.get('name'):
                m[norm(a['name'])] = c
        if e.get('english'):
            m[norm(e['english'])] = c
    t = jsons.get('표기_원장.json') or {}
    for k, v in (t.get('표기_통합') or {}).items():
        m[norm(k)] = v
        m[norm(v)] = v
    return m


def keys(name, amap):
    """대조에 쓸 열쇠들. 갈래마다 괄호 약칭을 붙이기도 떼기도 한다 —
       연대기는 '중동호흡기증후군(MERS)', 시뮬레이터는 '중동호흡기증후군'이다.
       그래서 붙인 것과 뗀 것을 둘 다 열쇠로 삼는다."""
    out = set()
    raw = name or ''
    bare = re.sub(r'\([^)]*\)', '', raw)          # 괄호째 떼기
    latin = re.sub(r'[A-Za-z]+', '', bare)        # 도감은 이미 괄호를 지운 채 약칭만 남긴다
    for v in (raw, bare, latin):
        k = norm(v)
        if not k:
            continue
        out.add(k)
        c = amap.get(k)
        if c:
            out.add(norm(c))
            out.add(norm(re.sub(r'\([^)]*\)', '', c)))
    return out


def module_names(jsons):
    """갈래마다 부르는 감염병 이름을 모은다. 없는 갈래는 건너뛴다."""
    out = {}

    chron = jsons.get('연대기.json') or {}
    if chron.get('diseases'):
        out['연대기'] = [d['name'] for d in chron['diseases'] if d.get('name')]

    try:
        from build_field_page import dogam_fields
        out['도감'] = list(dogam_fields().keys())          # 이미 정규화된 열쇠
    except Exception as e:                                # noqa: BLE001
        warn('도감', f'질병 목록을 읽지 못함 — {e}')

    sim = os.path.join(ROOT, '17_유행_시뮬레이터', 'data', '모형_매개변수.json')
    if os.path.exists(sim):
        P = json.load(open(sim, encoding='utf-8'))
        out['시뮬레이터'] = [d['name'] for d in P.get('diseases', [])]

    vac = jsons.get('백신_감염병_연결.json')
    if isinstance(vac, dict):
        cand = vac.get('links') or vac.get('entries') or []
        names = [x.get('disease') or x.get('감염병') for x in cand if isinstance(x, dict)]
        if any(names):
            out['예방접종'] = [n for n in names if n]
    return out


def check_names(jsons, csvs):
    amap = alias_map(jsons)
    mods = module_names(jsons)
    if '연대기' not in mods:
        err('이름 대조', '연대기.json에서 기준 목록을 얻지 못해 대조를 건너뛴다')
        return
    base = set()
    for n in mods['연대기']:
        base |= keys(n, amap)
    note(f'기준 목록 — 연대기 {len(base)}종 · 별칭 대응 {len(amap)}개')

    for mod, names in mods.items():
        if mod == '연대기':
            continue
        miss = sorted({n for n in names if not (keys(n, amap) & base)})
        # 도감은 법정감염병이 아닌 항목도 싣는다. 시뮬레이터는 담는 범위가 좁다.
        if miss:
            head = ', '.join(miss[:6]) + (f' 외 {len(miss)-6}개' if len(miss) > 6 else '')
            (warn if mod == '도감' else err)(f'이름 대조·{mod}',
                                            f'연대기에서 못 찾는 이름 {len(miss)}개 — {head}')
        else:
            note(f'{mod}: {len(names)}개 이름이 모두 연대기와 닿는다')

    # 연보 표의 감염병명도 본다
    yb = csvs.get('전수감시_신고수_2016_2025.csv')
    if yb:
        col = '감염병명' if '감염병명' in yb[0] else next((c for c in yb[0] if '명' in (c or '')), None)
        if col:
            names = [re.sub(r'\([A-Za-z0-9\-]+\)', '', r[col] or '') for r in yb]
            miss = sorted({n.strip() for n in names if n.strip() and not (keys(n, amap) & base)})
            if miss:
                head = ', '.join(miss[:6]) + (f' 외 {len(miss)-6}개' if len(miss) > 6 else '')
                warn('이름 대조·연보', f'연대기에서 못 찾는 이름 {len(miss)}개 — {head}')
            else:
                note(f'연보: {len(names)}개 이름이 모두 연대기와 닿는다')


# ── 4. 포털 각 쪽 ────────────────────────────────────────────────────────
def check_pages():
    n = 0
    for dirpath, _, fs in os.walk(PORTAL):
        for f in fs:
            if f != 'index.html':
                continue
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, ROOT)
            s = open(p, encoding='utf-8').read()
            n += 1
            if '<meta charset' not in s.lower():
                err(rel, '<meta charset>이 없다')
            if not re.search(r'<html[^>]*lang=', s):
                err(rel, '<html lang>이 없다')
            m = re.search(r'<title>(.*?)</title>', s, re.S)
            if not m or not m.group(1).strip():
                err(rel, '<title>이 비어 있다')
            if not re.search(r'<meta name="description"', s):
                warn(rel, 'description이 없다 — 검색 결과에 요약이 안 나온다')
            for bad in re.findall(r'(?:href|src)="(/[^/][^"]*)"', s):
                err(rel, f'루트절대 경로 — {bad}')
            ids = re.findall(r'\sid="([^"]+)"', s)
            dup = sorted({i for i in ids if ids.count(i) > 1})
            if dup:
                err(rel, f'중복 id — {dup[:5]}')
    note(f'포털 {n}쪽 확인')


# ── 5. 데이터 센터가 내건 파일이 실제로 있는가 ───────────────────────────
def check_data_page():
    """데이터 센터가 내건 목록은 쪽 안의 자바스크립트 값에 들어 있다.
       href만 훑으면 `files/${...}` 같은 템플릿 문자열을 파일 이름으로 오해한다."""
    p = os.path.join(PORTAL, 'data', 'index.html')
    if not os.path.exists(p):
        err('data/', '데이터 센터 쪽이 없다')
        return
    s = open(p, encoding='utf-8').read()
    m = re.search(r'const D = (\{.*?\});\n', s, re.S)
    if not m:
        err('data/', '쪽에서 자료 목록을 찾지 못했다 — 템플릿이 바뀌었나')
        return
    try:
        D = json.loads(m.group(1))
    except Exception as e:                               # noqa: BLE001
        err('data/', f'자료 목록을 읽지 못함 — {e}')
        return
    listed = set()
    for g in D.get('groups', []):
        for it in g.get('items', []):
            for fl in it.get('files', []):
                if fl.get('f'):
                    listed.add(fl['f'])
            repo = it.get('repo')
            if repo and not os.path.exists(os.path.join(ROOT, repo)):
                err('data/', f'저장소 경로가 없다 — {repo}')
            if not it.get('src'):
                warn('data/', f"{it.get('name')}: 출처가 비어 있다")
    for f in sorted(listed):
        if not os.path.exists(os.path.join(FILES, f)):
            err('data/', f'내걸었는데 파일이 없다 — {f}')
    have = set(os.listdir(FILES)) if os.path.isdir(FILES) else set()
    orphan = sorted(have - listed)
    if orphan:
        warn('data/', f'파일은 있는데 쪽에서 안 내건 것 {len(orphan)}개 — {", ".join(orphan[:5])}')
    if D.get('total_files') and D['total_files'] != len(listed):
        warn('data/', f"쪽이 적은 파일 수 {D['total_files']} 와 실제 목록 {len(listed)} 가 다르다")
    note(f'데이터 센터가 내건 파일 {len(listed)}개 · 자료 묶음 {sum(len(g.get("items", [])) for g in D.get("groups", []))}개')


# ── 6. 쉬운 말 — 어려운 낱말에 풀이가 있는가 ────────────────────────────
def check_plain_words():
    """본문에 나오는 어려운 말 가운데 풀이가 없는 것을 알려 준다.

    화면 글자가 아니라 원본 HTML을 훑으므로 대강의 수만 본다. 그래도
    '풀이가 통째로 빠진 말'은 이걸로 잡힌다.
    """
    try:
        from plain_glossary import TERMS, WATCH
    except Exception as e:                               # noqa: BLE001
        warn('쉬운 말', f'풀이 사전을 읽지 못함 — {e}')
        return
    used, nogloss = set(), {}
    for dirpath, _, fs in os.walk(PORTAL):
        for f in fs:
            if f != 'index.html':
                continue
            s = open(os.path.join(dirpath, f), encoding='utf-8').read()
            # 주입한 사전 자체는 빼고 센다
            s = re.sub(r'<script>\s*/\* 쉬운 말 풀이.*?</script>', '', s, flags=re.S)
            for w in WATCH:
                if w in s:
                    used.add(w)
                    if w not in TERMS:
                        nogloss[w] = nogloss.get(w, 0) + 1
    for w, n in sorted(nogloss.items(), key=lambda x: -x[1]):
        warn('쉬운 말', f'풀이가 없는 말 — {w} ({n}쪽)')
    idle = [t for t in TERMS if t not in used]
    if idle:
        note(f'쓰이지 않는 풀이 {len(idle)}개 — {", ".join(idle[:6])}')
    note(f'풀이 {len(TERMS)}개 · 본문에 나온 어려운 말 {len(used)}개 · 풀이 없는 말 {len(nogloss)}개')


def main():
    csvs, jsons = check_files()
    check_years(csvs)
    check_names(jsons, csvs)
    check_pages()
    check_data_page()
    check_plain_words()

    print('── 자료 점검 ' + '─' * 50)
    for m in NOTES:
        print(f'  · {m}')
    if WARNS:
        print(f'\n── 살펴볼 것 {len(WARNS)}건 ' + '─' * 40)
        for w, m in WARNS:
            print(f'  ! {w}: {m}')
    if ERRORS:
        print(f'\n── 고쳐야 할 것 {len(ERRORS)}건 ' + '─' * 40)
        for w, m in ERRORS:
            print(f'  ✗ {w}: {m}')
        print(f'\n결과: 오류 {len(ERRORS)}건 · 경고 {len(WARNS)}건')
        return 1
    print(f'\n결과: 오류 없음 · 경고 {len(WARNS)}건')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
