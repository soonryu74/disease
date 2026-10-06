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


def check_evidence():
    """근거 원장이 지켜야 할 것들.

    이 사이트가 틀렸던 방식은 '구조에서 사실을 추론'하는 것이었다.
    급수로 격리를 정하고, 잠복기로 감시 종료일을 정했다. 그 길을 다시 열지 않도록
    여기서 막는다 — 원장을 거치지 않은 임상 값이 화면에 나가면 오류다.
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import evidence as EV

    st = EV.stats()
    note(f"근거 원장: 문서 {st['docs']}건 · 격리 {st['isolation']}종 · 접촉자 {st['contact']}종")

    # 1) 출처 없는 임상 값이 나가지 않는가
    for name in ('탄저', '보툴리눔독소증', '야토병'):
        r = EV.isolation(name)
        if not r['ok']:
            err('근거 원장', f'{name} 격리 근거가 사라졌다')
        elif '격리가 불필요' not in (r['isolation'] or ''):
            err('근거 원장', f"{name} 격리 값이 공식 지침과 다르다: {r['isolation']}")
    # 원장에 없는 질환은 반드시 빈 자리가 나와야 한다.
    # (전에는 '에볼라·MERS 는 비어 있어야 한다'고 못 박아 두었는데, 그건 그때의 형편이지
    #  지켜야 할 규칙이 아니었다. 근거를 찾아 채우자 이 점검이 틀렸다고 울었다.
    #  규칙은 '원장에 없으면 값이 안 나간다'이지 '이 질환은 비어 있어야 한다'가 아니다.)
    # 표본을 손으로 적어 두면 근거를 채울 때마다 이 점검이 틀렸다고 운다.
    # (두 번 그랬다 — 에볼라·MERS 때 한 번, 파라티푸스 때 또 한 번.)
    # 그래서 '원장에 아직 없는 질환'을 그때그때 골라 본다.
    chron = json.load(open(os.path.join(ROOT, '09_감염병연대기', 'data', '연대기.json'),
                           encoding='utf-8'))
    absent = [d['name'] for d in chron['diseases'] if EV.norm(d['name']) not in EV.ISO][:5]
    for name in absent:
        r = EV.isolation(name)
        if r['ok']:
            err('근거 원장', f'{name} 은 원장에 없는데 격리 값이 나간다')
        elif not r.get('where'):
            err('근거 원장', f'{name} 의 빈 자리에 확인 경로가 없다')

    # 2) 모든 근거에 출처·쪽수·검토상태가 붙어 있는가
    for sec in ('격리_및_감염관리', '접촉자_관리'):
        for row in EV.L[sec]['항목']:
            who = row.get('질병', '?')
            for f in ('출처', '쪽', '검토상태', '검토일'):
                if not row.get(f):
                    err('근거 원장', f'{sec} {who}: {f} 가 비었다')
            if row.get('출처') not in EV.DOCS:
                err('근거 원장', f'{sec} {who}: 모르는 문서 {row.get("출처")}')

    # 3) 현장카드가 급수로 격리를 추론하고 있지 않은가
    fp = os.path.join(ROOT, 'portal', 'field', 'index.html')
    if os.path.exists(fp):
        t = open(fp, encoding='utf-8').read()
        i = t.find('const D = ')
        if i > 0:
            D = json.loads(t[i + 10:t.index('\n', i)].rstrip(';').replace('<\\/', '</'))
            cards = D['cards']
            bad = [c['disease'] for c in cards
                   if c['iso'].get('ok') and EV.norm(c['disease']) not in EV.ISO]
            if bad:
                err('현장카드', f'원장에 없는데 격리 값이 붙은 카드: {bad}')
            g1 = [c for c in cards if (c.get('grade') or '') == '제1급']
            blanket = [c['disease'] for c in g1
                       if c['iso'].get('ok') and c['iso'].get('isolation') == '음압격리']
            if blanket:
                err('현장카드', f'제1급 일괄 음압격리가 되살아났다: {blanket}')
            note(f"현장카드 {len(cards)}종 — 격리 근거 있음 "
                 f"{sum(1 for c in cards if c['iso'].get('ok'))}종 · "
                 f"확인 필요 {sum(1 for c in cards if not c['iso'].get('ok'))}종")

    # 3-2) 검체 표가 스스로 검산한 것만 싣는가
    if EV.SPEC:
        bad = [k for k, v in EV.SPEC.items()
               if v.get('채취조건') and not v.get('검체')]
        if bad:
            err('검체', f'검체 목록 없이 표만 실린 질환 {len(bad)}종')
        rows = sum(len(v.get('채취조건') or []) for v in EV.SPEC.values())
        drop = sum(v.get('검산_버린행') or 0 for v in EV.SPEC.values())
        clean_dz = sum(1 for v in EV.SPEC.values()
                       if v.get('채취조건') and not v.get('표_확인필요'))
        note(f'검체: 질환 {len(EV.SPEC)}종 · 표 {rows}행 실음 · 검산에서 버린 행 {drop}개 · '
             f'버린 행 없이 깨끗한 질환 {clean_dz}종')
        # 실은 행의 검체명은 반드시 그 질환의 '검체' 목록 안에 있어야 한다
        for k, v in EV.SPEC.items():
            decl = re.sub(r'[,·]', ' ', v.get('검체') or '')
            for r in (v.get('채취조건') or []):
                nm = r.get('검체') or ''
                if nm and nm not in decl and not any(nm in w or w in nm
                                                     for w in decl.split() if len(w) > 1):
                    err('검체', f'{k}: 표의 "{nm}" 가 검체 목록에 없다')
                    break

    # 4) 검역 '현행'이 날짜로 정해지는가
    hp = os.path.join(ROOT, '11_검역관리지역', 'data', '지정이력.json')
    if os.path.exists(hp):
        h = json.load(open(hp, encoding='utf-8'))
        hard = [p['period'] for p in h['periods'] if '현행' in (p.get('note') or '')]
        if hard:
            err('검역', f"자료에 '현행'이라 적어 둔 시기가 있다 — 날짜로 정해야 한다: {hard}")
        today = date.today().isoformat()
        eff = [p for p in h['periods'] if (p.get('effective') or '') <= today]
        if eff:
            cur = max(eff, key=lambda p: p['effective'])
            note(f"검역 현행: {cur['period']} ({cur['effective']} 시행) · "
                 f"중점 {cur['priority']['countries']}개국 · 검역 {cur['general']['countries']}개국")

    # 5) 병원체 무리 이름이 국내 질환을 확정하고 있지 않은가
    import fetch_daily as FD
    groups = {k for k, _c, _w in FD.PATHOGEN_GROUP_KW}
    for k, _d in FD.DISEASE_KW:
        if k in groups:
            err('상황판', f"'{k}' 가 병원체 무리이면서 질환 확정 목록에도 있다")


def main():
    csvs, jsons = check_files()
    check_years(csvs)
    check_names(jsons, csvs)
    check_pages()
    check_data_page()
    check_plain_words()
    check_evidence()

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
