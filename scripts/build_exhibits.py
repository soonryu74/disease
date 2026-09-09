#!/usr/bin/env python3
"""연대기 전시물 원장 — 흩어진 자료에서 '그 해에 무슨 일이 있었나'를 뽑는다.

지침 2,347건과 백서 19판을 모아 두는 것 자체는 목적이 아니었다. 목적은 그 안의 내용을
**연도별로 무엇이 달라졌는지** 보이게 만드는 것이다. 그래서 목록이 아니라 **전시물**을 만든다.

전시물은 여섯 갈래로 나눈다.
  제도  법령 제·개정, 고시, 급수·감시체계 변동, 단절점
  유행  그 해 급증한 감염병, 최다 발생
  지침  그 해 게시판에 처음 나타난 지침 계열, 그 해의 발간량
  기록  질병관리청 백서 발간(표지가 곧 전시물이다)
  접종  국가예방접종 대상 추가, 완전접종률
  검역  검역관리지역 제도 변경

각 전시물에는 **원문 링크**를 단다. 자료를 여기 쌓아 두는 것이 아니라
"무슨 일이 있었고, 원문은 여기 있다"를 보여 주는 것이 이 원장의 일이다.

산출: 09_감염병연대기/data/전시물.json
"""
import csv
import json
import math
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '09_감염병연대기', 'data', '전시물.json')

CHRON = os.path.join(ROOT, '09_감염병연대기', 'data', '연대기.json')
GRADE = os.path.join(ROOT, '01_감염병예방법_연혁', 'data', '급수변동_이력.json')
GOSI = os.path.join(ROOT, '01_감염병예방법_연혁', 'data', '감염병지정고시_연혁.json')
LAW = os.path.join(ROOT, '01_감염병예방법_연혁', 'data', '감염병예방법_연혁_전체.csv')
GUIDE = os.path.join(ROOT, '02_지침_정리', 'data', '지침_통합목록.csv')
WP = os.path.join(ROOT, '03_백서_정리', 'data', '백서_목록.json')
CASES = os.path.join(ROOT, '03_백서_정리', 'data', '전수감시_신고수_2016_2025.csv')
QUAR = os.path.join(ROOT, '11_검역관리지역', 'data', '지정이력.json')
VACC = os.path.join(ROOT, '18_예방접종', 'data', '어린이_예방접종률.json')

# 미술관 벽에 붙는 작품 설명처럼, 갈래마다 '이걸 어떻게 볼 것인가'를 적어 둔다.
# 사건 자체(body)와 보는 법(why)을 나눈다 — 섞으면 사실과 해석이 붙어 버린다.
CURATOR = {
    'law': ('급이 바뀌면 신고 시기·격리 수준·통계를 세는 분모가 함께 바뀐다. '
            '그래서 이 날 앞뒤의 숫자는 같은 것을 세지 않는다. '
            '“이 감염병은 몇 급인가”가 아니라 “언제의 몇 급인가”를 물어야 한다.'),
    'outbreak': ('배수는 분모가 작을 때 크게 나온다. 전년에 거의 없던 감염병일수록 배수가 커 보이므로 '
                 '규모는 실제 건수로 확인해야 한다. 또 그 해에 신고 기준이나 감시체계가 바뀌었다면 '
                 '늘어난 것이 발생인지 집계인지부터 갈라야 한다.'),
    'guide': ('지침이 처음 나온 해는 그 감염병이 “관리 대상”이 된 해다. '
              '다만 이 목록은 게시판에 남아 있는 것 기준이라, 게시판이 시작되기 전에 나온 지침은 보이지 않는다. '
              '‘처음’은 발간의 처음이 아니라 기록의 처음일 수 있다.'),
    'record': ('백서는 그 해를 국가가 스스로 정리한 기록이다. 무엇을 성과로 적었는지와 함께 '
               '무엇을 적지 않았는지가 읽힌다. 백서의 “향후 추진계획”은 다음 해 제도 변화의 예고편이기도 하다.'),
    'vacc': ('완전접종률은 접종률이 아니다. 그 나이까지 맞아야 할 백신을 하나도 빠짐없이 마쳐야 완전접종이므로, '
             '세는 백신이 늘면 접종을 똑같이 해도 값은 내려간다.'),
    'border': ('검역관리지역은 “어디서 오는 사람을 더 볼 것인가”의 목록이다. '
               '국가 수만 연도별로 비교하면 제도 자체가 바뀐 해를 놓친다.'),
}
# 전시물마다 붙이는 '함께 볼 것'
SEE = {
    'law': [('단절점 검사기', '../checker/'), ('법령 연혁', '../law/'), ('연대기', '../chronicle/')],
    'outbreak': [('교차검증', '../cross/'), ('유행 시뮬레이터', '../sim/'), ('단절점 검사기', '../checker/')],
    'guide': [('지침 서가', '../guides/'), ('현장카드', '../field/')],
    'record': [('백서 서가', '../whitepaper/'), ('연대기', '../chronicle/')],
    'vacc': [('예방접종', '../vaccine/'), ('유행 시뮬레이터', '../sim/')],
    'border': [('검역', '../quarantine/'), ('해외유입 지도', '../inflow/'), ('정책 실험실', '../policy/')],
}

THEMES = [
    ('law', '제도', '#6A4C93', '법률·고시·급수와 감시체계가 바뀐 날'),
    ('outbreak', '유행', '#B23A3A', '그 해 두드러지게 늘어난 감염병'),
    ('guide', '지침', '#0E6E63', '그 해 처음 나온 관리·대응지침'),
    ('record', '기록', '#B8942A', '질병관리청 백서 — 그 해를 정리한 공식 기록'),
    ('vacc', '접종', '#2F7D8C', '국가예방접종에 무엇이 더해졌나'),
    ('border', '검역', '#C7712B', '국경에서의 규칙이 바뀐 날'),
]
LAWDOC = 'https://www.law.go.kr/법령/감염병의예방및관리에관한법률'


def norm(s):
    """'코로나19'와 '코로나바이러스감염증-19'를 같은 것으로 보기 위한 최소 정규화"""
    return re.sub(r'[\s()·・\-—,]|감염증|바이러스|감염|증$', '', s or '')


def same(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or a in b or b in a)


def add(ex, **k):
    k.setdefault('link', '')
    k.setdefault('art', '')
    ex.append(k)


# ── 제도 ────────────────────────────────────────────────────────────
def from_law(ex):
    c = json.load(open(CHRON, encoding='utf-8'))
    for e in c['epochs']:
        y = int(e['y'][:4])
        add(ex, y=y, date=e['y'], theme='law', w=100, tag='시대 구분',
            title=e['t'], body=e['d'], link=LAWDOC,
            why='체계가 바뀐 해다. 감염병의 이름과 급, 세는 방법이 한꺼번에 다시 짜였으므로 '
                '이 선을 넘어 숫자를 이으면 거의 언제나 틀린다. 연대기가 “언제의 사실인가”를 '
                '먼저 묻는 이유가 여기에 있다.')

    g = json.load(open(GRADE, encoding='utf-8'))
    W = {'new': 95, 'up': 90, 'down': 92, 'surveillance': 86, 'scope': 76}
    NAME = {'new': '신규 지정', 'up': '급 상향', 'down': '급 하향',
            'surveillance': '감시체계 전환', 'scope': '신고범위 변경'}
    for e in g['events']:
        y = int(e['date'][:4])
        gr = e.get('grade') or [None, None]
        sv = e.get('surv') or [None, None]
        bits = []
        if gr[0] != gr[1]:
            bits.append(f"{gr[0] or '비법정'} → {gr[1]}")
        if sv[0] != sv[1]:
            bits.append(f"{sv[0] or '—'}감시 → {sv[1]}감시")
        if e.get('scope'):
            bits.append(e['scope'])
        add(ex, y=y, date=e['date'], theme='law', w=W.get(e['change'], 70),
            tag=NAME.get(e['change'], e['change']),
            title=f"{e['disease']} — {NAME.get(e['change'], e['change'])}",
            body=' · '.join(bits) + (f"\n{e['note']}" if e.get('note') else ''),
            link=LAWDOC)

    # 단절점 원장은 급수변동에서 파생된 것이 많다. 같은 날 같은 감염병이면 한 번만 건다.
    done = {(e['date'], norm(e['disease'])) for e in g['events']}
    for b in c['breaks']:
        if any(b['date'] == d and same(b['disease'], n) for d, n in done):
            continue
        y = int(b['date'][:4])
        add(ex, y=y, date=b['date'], theme='law', w=74, tag='단절점',
            title=f"{b['disease']} — {b['title']}",
            body='이 날 앞뒤로 숫자의 뜻이 달라진다. 그냥 이으면 유행을 잘못 읽는다.',
            link='../checker/')

    # 법률 본문이 통째로 바뀐 해만. 일부개정은 100건이 넘어 전시물이 되지 못한다.
    for r in csv.DictReader(open(LAW, encoding='utf-8-sig')):
        if r['제개정구분'] not in ('제정', '전부개정') or not r['법령명'].startswith(('전염병예방법', '감염병의 예방')):
            continue
        if r['법령구분'] != '법률':
            continue
        d = r['공포일자']
        add(ex, y=int(d[:4]), date=f'{d[:4]}-{d[4:6]}-{d[6:]}', theme='law', w=88,
            tag=r['제개정구분'], title=f"{r['법령명']} {r['제개정구분']}",
            body=f"공포 {d[:4]}.{d[4:6]}.{d[6:]} · 시행 {r['시행일자'][:4]}.{r['시행일자'][4:6]}.{r['시행일자'][6:]}"
                 f" · 법률 제{int(r['공포번호'])}호",
            link=LAWDOC)

    gs = json.load(open(GOSI, encoding='utf-8'))
    for e in gs['gosi']:
        d = e['date']
        add(ex, y=int(d[:4]), date=f'{d[:4]}-{d[4:6]}-{d[6:]}', theme='law', w=70,
            tag='고시', title=f"{e['name']} ({e['no']}호)",
            body='질병관리청장이 지정하는 감염병의 종류 — 법률 열거 밖의 감염병은 이 고시로 정해진다.',
            link='../law/')


# ── 유행 ────────────────────────────────────────────────────────────
def from_cases(ex):
    rows = list(csv.DictReader(open(CASES, encoding='utf-8-sig')))
    years = [k for k in rows[0] if k.isdigit()]

    def num(r, y):
        v = (r.get(y) or '').replace(',', '').strip()
        return int(v) if v.isdigit() else None

    for i, y in enumerate(years):
        yi = int(y)
        vals = [(r['감염병명'], num(r, y), num(r, years[i - 1]) if i else None, r['급'])
                for r in rows]
        # 급증 — 3배 이상 늘고 100건을 넘은 것
        surged = set()
        for name, cur, prev, grade in vals:
            if not cur or not prev or prev < 5 or cur < 100:
                continue
            r = cur / prev
            if r < 3:
                continue
            surged.add(name)
            add(ex, y=yi, date=y, theme='outbreak',
                w=min(96, 68 + 12 * math.log10(r)), tag='급증',
                title=f'{name} {r:.1f}배',
                body=f'{int(y)-1}년 {prev:,}명 → {y}년 {cur:,}명({grade}). 그 해 가장 크게 늘어난 감염병이다.',
                link='../cross/')
        # 그 해 최다 — 급증으로 이미 건 감염병이면 같은 얘기가 되므로 건너뛴다
        top = max((v for v in vals if v[1] is not None and v[0] not in surged),
                  key=lambda v: v[1], default=None)
        if top and top[1] > 0:
            add(ex, y=yi, date=y, theme='outbreak', w=62, tag='최다 발생',
                title=f'{top[0]} {top[1]:,}명',
                body=f'{y}년 전수감시 신고가 가장 많았던 감염병({top[3]}).',
                link='../cross/')


# ── 지침 ────────────────────────────────────────────────────────────
GUIDE_KIND = re.compile(r'관리지침|대응지침|방역지침|관리\s*지침|대응\s*지침|안내서|매뉴얼')


def from_guides(ex):
    rows = [r for r in csv.DictReader(open(GUIDE, encoding='utf-8-sig'))
            if r['분야'] == '감염병']
    ser = defaultdict(list)
    for r in rows:
        ser[r['계열키']].append(r)
    per_year = defaultdict(int)
    for r in rows:
        per_year[int(r['연도'])] += 1

    for k, rs in ser.items():
        rs.sort(key=lambda r: (int(r['연도']), r['등록일']))
        n = len(rs)
        first = rs[0]
        if n < 3 or not GUIDE_KIND.search(first['제목']):
            continue                       # 오래 이어진 '지침'만 전시물로 삼는다
        y = int(first['연도'])
        add(ex, y=y, date=first['등록일'].replace('.', '-'), theme='guide',
            w=min(84, 52 + n * 2), tag=f'{n}판 이어짐',
            title=first['제목'],
            body=f'이 계열이 게시판에 처음 나타난 해다. {y}년부터 {rs[-1]["연도"]}년까지 {n}판.',
            link=first['URL'])

    for y, n in per_year.items():
        if n < 30:
            continue
        add(ex, y=y, date=str(y), theme='guide', w=48, tag='발간량',
            title=f'{y}년 지침·자료 {n}건',
            body='그 해 질병관리청 게시판에 오른 감염병 지침·서식·교육자료의 수다.',
            link='../guides/')


# ── 기록(백서) ──────────────────────────────────────────────────────
def from_whitepaper(ex):
    if not os.path.exists(WP):
        return
    j = json.load(open(WP, encoding='utf-8'))
    for it in j['items']:
        m = re.match(r'(\d{4})(?:~(\d{4}))?년\s*(.*)', it['label'])
        if not m or '[' in it['label']:
            continue                       # 국문판만. 영문·텍스트판은 같은 사건이다
        y = int(m.group(1))
        span = f"{m.group(1)}~{m.group(2)}" if m.group(2) else m.group(1)
        art = '../whitepaper/covers/' + it['cover_file'] if it.get('cover_file') else ''
        if it['hidden']:
            add(ex, y=y, date=str(y), theme='record', w=72, tag='원문 유실',
                title=f'{span}년 백서 — 표지만 남았다',
                body='게시판 소스에 항목이 주석으로 감싸여 화면에 보이지 않고, 내려받기 주소도 비어 있다. '
                     '표지 이미지는 서버에 살아 있어 발간 사실만 확인된다.',
                link='../whitepaper/', art=art,
                why='이 액자에는 표지만 걸려 있다. 본문이 없기 때문이다. '
                    '유실된 아홉 판은 신종플루(2009)·결핵 정점(2011)·메르스(2015)를 통째로 덮는다. '
                    '기록이 사라진 자리를 비워 두는 것도 전시의 일이다 — 없는 것을 있는 것처럼 채우지 않는다.')
        else:
            add(ex, y=y, date=str(y), theme='record', w=66, tag='백서 발간',
                title=f'{span}년 {m.group(3) or "백서"}',
                body='그 해의 활동을 질병관리청이 스스로 정리한 공식 기록이다.',
                link=it['file'] or '../whitepaper/', art=art)


# ── 접종 ────────────────────────────────────────────────────────────
def from_vacc(ex):
    if not os.path.exists(VACC):
        return
    j = json.load(open(VACC, encoding='utf-8'))
    eds = sorted(j['editions'], key=lambda e: e['year'])
    prev = set()
    for e in eds:
        vs = {v for v in e['vaccines'] if v != '완전접종률'}
        new = sorted(vs - prev) if prev else []
        if new:
            add(ex, y=e['year'], date=str(e['year']), theme='vacc', w=78,
                tag='완전접종 기준 확대',
                title=f"완전접종에 {', '.join(new)} 추가",
                body=f"{e['year']}년부터 {len(vs)}종을 모두 마쳐야 완전접종이다. "
                     f"기준이 무거워졌으므로 앞 해의 접종률과 그냥 견주면 안 된다.",
                link='../vaccine/')
        prev = vs
    comp = defaultdict(dict)
    for r in j['rows']:
        if r['항목'] == '접종률' and r['백신'] == '완전접종률':
            comp[r['연도']][r['연령']] = r['값']
    for y, m in sorted(comp.items()):
        if not m:
            continue
        lo = min(m.items(), key=lambda kv: kv[1])
        add(ex, y=y, date=str(y), theme='vacc', w=50, tag='완전접종률',
            title=f'{lo[0]} 완전접종률 {lo[1]}%',
            body='그 해 조사 연령 가운데 가장 낮은 값. 나이가 올라 맞을 것이 늘수록 값은 내려간다.',
            link='../vaccine/')


# ── 검역 ────────────────────────────────────────────────────────────
def from_quarantine(ex):
    if not os.path.exists(QUAR):
        return
    j = json.load(open(QUAR, encoding='utf-8'))
    for b in j.get('structural_breaks', []):
        y = int(b['date'][:4])
        add(ex, y=y, date=b['date'], theme='border', w=80, tag='검역 제도',
            title=b['title'], body=(b.get('detail') or ''), link='../quarantine/',
            why=(b.get('impact') or '') + ('\n' + b['caveat'] if b.get('caveat') else '')
                or CURATOR['border'])
    for p in j.get('periods', []):
        note = p.get('note') or ''
        g = p.get('general') or {}
        if not note or not p.get('effective'):
            continue
        y = int(p['effective'][:4])
        add(ex, y=y, date=p['effective'], theme='border', w=52, tag='지정 갱신',
            title=f"{p['period']} 검역관리지역 " +
                  (f"{g['countries']}개국" if g.get('countries') else '지정'),
            body=note, link='../quarantine/')


def build():
    ex = []
    from_law(ex)
    from_cases(ex)
    from_guides(ex)
    from_whitepaper(ex)
    from_vacc(ex)
    from_quarantine(ex)

    # 같은 해에 같은 것을 두 번 걸지 않는다. 갈래가 달라도 사건이 같으면 하나만.
    seen, uniq = set(), []
    for e in sorted(ex, key=lambda e: -e['w']):
        base = re.sub(r'[\s\d]', '', e['title'])[:24]
        if any(y == e['y'] and same(base, b) for y, b in seen):
            continue
        seen.add((e['y'], base))
        uniq.append(e)

    # 작품 설명 — 갈래별 기본 해설에, 전시물이 스스로 가진 단서를 앞에 붙인다
    for e in uniq:
        e['why'] = e.get('why') or CURATOR.get(e['theme'], '')
        e['see'] = SEE.get(e['theme'], [])

    by = defaultdict(list)
    for e in uniq:
        by[e['y']].append(e)
    years = []
    for y in sorted(by):
        items = sorted(by[y], key=lambda e: (-e['w'], e['date']))
        # 10대 뉴스가 한 갈래로 채워지지 않게 한다. 지침은 해마다 수십 건이라
        # 가중치만으로 고르면 열 자리를 지침이 다 먹는다.
        top, used = [], defaultdict(int)
        for cap in (3, 5, 99):                 # 갈래당 3점까지 → 5점까지 → 나머지
            for it in items:
                if len(top) >= 10:
                    break
                if it in top or used[it['theme']] >= cap:
                    continue
                top.append(it)
                used[it['theme']] += 1
        top.sort(key=lambda e: (-e['w'], e['date']))
        for i, it in enumerate(top):
            it['rank'] = i + 1
        years.append({'y': y, 'n': len(items), 'top': top,
                      'rest': len(items) - len(top),
                      'themes': sorted({i['theme'] for i in top})})

    tcount = defaultdict(int)
    for e in uniq:
        tcount[e['theme']] += 1
    data = {
        'as_of': '2026-09',
        'span': [years[0]['y'], years[-1]['y']],
        'total': len(uniq),
        'themes': [{'k': k, 'name': n, 'color': c, 'desc': d, 'n': tcount[k]}
                   for k, n, c, d in THEMES],
        'years': years,
        'note': '전시물은 저장소의 원장(법령 연혁·급수변동·지침 목록·백서 목록·연보 신고수·'
                '검역 지정이력·예방접종률)에서 기계로 뽑았다. 순위는 갈래별 가중치이며 '
                '중요도의 객관적 척도가 아니다 — 무엇을 큰일로 볼지는 보는 사람이 정한다.',
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f"전시물 {len(uniq):,}점 · {data['span'][0]}~{data['span'][1]}년 {len(years)}개 전시실")
    print('  갈래 ' + ' · '.join(f'{n} {tcount[k]}' for k, n, _, _ in THEMES))
    thin = [y['y'] for y in years if y['n'] < 3]
    print(f"  전시물 3점 미만인 해 {len(thin)}개: {', '.join(map(str, thin[:14]))}"
          f"{' …' if len(thin) > 14 else ''}")
    for y in years[-4:]:
        print(f"  {y['y']}년 {y['n']}점 — " + ' / '.join(f"{i['title'][:26]}" for i in y['top'][:4]))
    print(f'  → {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,}B)')


if __name__ == '__main__':
    build()
