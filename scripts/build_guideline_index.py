#!/usr/bin/env python3
"""감염병별 지침 인덱스 — 358건의 관리지침을 법정감염병 91종에 연결한다.

대응 현장에서 필요한 것은 '지침 358건 목록'이 아니라 **"이 병이면 어느 지침을 펴야 하나"**다.
그래서 질병 → 지침 방향으로 뒤집는다.

## 연결 등급 (섞지 않는다)
 - `direct` — 지침 제목에 그 질병명이나 옛 이름·약어가 들어 있다. **사실**이다.
 - `group`  — 그 질병이 속한 계열의 묶음 지침(예: 호흡기감염병 관리지침)이다.
              묶음 지침이 실제로 어느 질병을 다루는지는 **원문 목차를 봐야** 확정된다.
              여기서는 '찾아볼 후보'로만 제시하고 그 사실을 표시한다.

추정으로 두 등급을 섞지 않는 것이 이 저장소의 원칙이다.
"""
import csv
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '02_지침_정리', 'data', '지침_통합목록.csv')   # 누리집 게시판 + 감염병포털
SRC_FALLBACK = os.path.join(ROOT, '02_지침_정리', 'data', '지침_전체목록_감염병포털.csv')
THIS_YEAR = 2026
CHRON = os.path.join(ROOT, '09_감염병연대기', 'data', '연대기.json')
ALIAS = os.path.join(ROOT, '05_감염병_질병정보', '별칭사전.json')
OUT = os.path.join(ROOT, '14_역학조사_실무', 'data')

# 묶음 지침 → 어느 계열을 찾는 사람에게 보여줄지. 계열 소속은 아래 GROUP_MEMBERS로 정의하고,
# '이 지침이 그 질병을 실제로 다루는지'는 원문 확인 사항으로 남긴다.
GROUP_PATTERNS = [
    ('호흡기', r'호흡기감염병'),
    ('수인성', r'수인성|식품매개'),
    # 2023년부터 A·B·C·E형간염이 수인성 지침에서 떨어져 나와 통합 간염 지침이 됐다
    ('간염', r'바이러스\s*간염|간염\s*관리지침|간염\s*\(A형'),
    ('예방접종', r'예방접종대상|국가예방접종|예방접종\s*사업'),
    ('성매개', r'성매개감염병|성병\s*관리'),
    ('의료관련', r'의료관련감염|항생제내성|내성균'),
    ('인수공통', r'인수공통'),
    ('모기매개', r'모기매개|매개모기|바이러스성\s*모기'),
    ('진드기설치류', r'진드기|설치류'),
    ('기생충', r'기생충감염병'),
    ('결핵', r'결핵\s*관리지침'),
    ('1급', r'제1급감염병\s*대응지침(?!\s*\()|제1급감염병\s*관리'),
    ('1급_출혈열', r'제1급감염병.*출혈열'),
    ('1급_생물테러', r'제1급감염병.*(두창|페스트|탄저|보툴리눔|야토)'),
    ('진단검사', r'진단검사\s*통합지침|진단[·・\s]*신고\s*기준|신고범위'),
    ('검역', r'검역업무|검역\s*지침'),
    ('위기대응', r'위기관리|위기대응|생물테러|원인불명|풍수해'),
]

# 계열별 소속 질병(현행 기준). 지침 제목에 병명이 없어도 이 계열 지침을 후보로 보여준다.
GROUP_MEMBERS = {
    '호흡기': ['인플루엔자', '코로나바이러스감염증-19', '급성호흡기감염증', '레지오넬라증',
             '중동호흡기증후군(MERS)', '중증급성호흡기증후군(SARS)', '신종인플루엔자',
             '동물인플루엔자 인체감염증', '결핵', '수두', '홍역', '백일해', '성홍열',
             '유행성이하선염', '풍진', '디프테리아', '수막구균 감염증', '폐렴구균 감염증',
             'b형헤모필루스인플루엔자'],
    '수인성': ['콜레라', '장티푸스', '파라티푸스', '세균성이질', '장출혈성대장균감염증',
             'A형간염', 'E형간염', '장관감염증', '노로바이러스 감염증', '살모넬라균 감염증',
             '캄필로박터균 감염증', '비브리오패혈증'],
    '간염': ['A형간염', 'B형간염', 'C형간염', 'E형간염'],
    '모기매개': ['말라리아', '일본뇌염', '뎅기열', '지카바이러스감염증', '치쿤구니야열', '황열',
              '웨스트나일열'],
    '진드기설치류': ['쯔쯔가무시증', '중증열성혈소판감소증후군(SFTS)', '신증후군출혈열', '렙토스피라증',
                '라임병', '진드기매개뇌염', '발진열', '발진티푸스', '야토병'],
    '기생충': ['회충증', '편충증', '요충증', '간흡충증', '폐흡충증', '장흡충증', '해외유입기생충감염증'],
    '결핵': ['결핵', '한센병'],
    '1급_출혈열': ['에볼라바이러스병', '마버그열', '라싸열', '크리미안콩고출혈열', '남아메리카출혈열',
                '리프트밸리열'],
    '1급_생물테러': ['두창', '페스트', '탄저', '보툴리눔독소증', '야토병'],
    '검역': ['콜레라', '페스트', '황열', '중증급성호흡기증후군', '중동호흡기증후군',
            '동물인플루엔자 인체감염증', '신종인플루엔자', '에볼라바이러스병', '마버그열', '라싸열',
            '크리미안콩고출혈열', '폴리오', '홍역', '뎅기열', '치쿤구니야열', '지카바이러스감염증',
            '니파바이러스감염증'],
    '예방접종': ['홍역', '풍진', '유행성이하선염', '수두', '백일해', '디프테리아', '파상풍',
              '폴리오', 'b형헤모필루스인플루엔자', '폐렴구균 감염증', 'B형간염', 'A형간염',
              '일본뇌염', '인플루엔자', '결핵', '사람유두종바이러스(HPV) 감염증'],
    '성매개': ['매독', '임질', '클라미디아감염증', '연성하감', '성기단순포진', '첨규콘딜롬',
             '사람유두종바이러스(HPV) 감염증', '후천성면역결핍증(AIDS)'],
    '의료관련': ['반코마이신내성황색포도알균(VRSA) 감염증', '카바페넴내성장내세균목(CRE) 감염증',
              '반코마이신내성장알균(VRE) 감염증', '메티실린내성황색포도알균(MRSA) 감염증',
              '다제내성녹농균(MRPA) 감염증', '다제내성아시네토박터바우마니균(MRAB) 감염증',
              '칸디다오리스감염증'],
    '인수공통': ['공수병', '브루셀라증', '탄저', '큐열', '중증열성혈소판감소증후군(SFTS)',
              '신증후군출혈열', '렙토스피라증', '동물인플루엔자 인체감염증', '니파바이러스감염증'],
    '매개체': ['말라리아', '일본뇌염', '쯔쯔가무시증', '중증열성혈소판감소증후군(SFTS)',
             '뎅기열', '지카바이러스감염증', '치쿤구니야열', '황열', '웨스트나일열', '라임병',
             '진드기매개뇌염', '발진티푸스', '발진열'],
}


def load_diseases():
    d = json.load(open(CHRON, encoding='utf-8'))
    out = []
    for x in d['diseases']:
        cur = None
        for p in x['phases']:
            if p.get('status', '').startswith('제'):
                cur = p['status']
        out.append({'name': x['name'], 'grade': cur, 'icon': x.get('icon', ''),
                    'names': [n['n'] for n in x.get('names', []) if n.get('n')]})
    return out


def load_aliases():
    try:
        j = json.load(open(ALIAS, encoding='utf-8'))
    except Exception:
        return {}
    m = {}
    for e in j.get('entries', []):
        names = [a['name'] for a in e.get('aliases', []) if a.get('name')]
        if e.get('english'):
            names.append(e['english'])
        m[e['canonical']] = names
    return m


def norm(s):
    return re.sub(r'[\s()·・\-]', '', s or '')


def keys_for(dz, aliases):
    """제목에서 찾을 검색어들 — 정식명·괄호 안 약어·옛 이름"""
    ks = set()
    name = dz['name']
    ks.add(name)
    ks.update(dz['names'])
    base = re.sub(r'\s*감염증$|\s*감염$', '', name)
    ks.add(base)
    for m in re.findall(r'\(([A-Za-z0-9/\-]{2,12})\)', name):
        ks.add(m)
    ks.add(re.sub(r'\([^)]*\)', '', name).strip())
    ks.update(aliases.get(name, []))
    ks.update(aliases.get(base, []))
    return {k for k in (x.strip() for x in ks) if len(norm(k)) >= 2}


def year_of(row):
    m = re.search(r'(20\d{2}|19\d{2})', row['제목'])
    if m:
        return int(m.group(1))
    return int(row['등록일'][:4]) if row.get('등록일', '')[:4].isdigit() else 0


# 게시판에는 지침만 있지 않다. 포스터·공모전·채용까지 섞여 있어 종류를 갈라 순위를 매긴다.
DOC_DROP = re.compile(r'공모전|채용|모집\s*공고|입찰|계약|낙찰|회의록|위원\s*위촉|설문|만족도|'
                      r'견적|용역\s*공고|사전규격|재공고|당첨|이벤트|기념일|캠페인\s*안내')
DOC_KINDS = [
    ('지침', re.compile(r'지침|매뉴얼|안내서|가이드(?!맵)|권고안|진료\s*가이드|표준\s*운영|'
                        r'진단[·・\s]*신고\s*기준|관리\s*기준|사업\s*안내')),
    ('서식', re.compile(r'서식|신고서|조사서|결과\s*보고서|양식|동의서|기록지|보고\s*서식')),
    ('교육홍보', re.compile(r'포스터|리플렛|리플릿|카드뉴스|웹툰|영상|홍보|교육자료|수칙|소책자|'
                         r'안내문|팩트시트|브로슈어|배너')),
]
KIND_RANK = {'지침': 0, '서식': 1, '교육홍보': 2, '기타': 3}


def doc_kind(title):
    for k, pat in DOC_KINDS:
        if pat.search(title):
            return k
    return '기타'


def series_key(title):
    """같은 지침의 판을 묶는 열쇠 — fetch_kdca_guides.key 와 같은 규칙"""
    t = re.sub(r'\(.*?\)|「|」|\[.*?\]', ' ', title)
    t = re.sub(r'(19|20)\d{2}\s*년도?|제\s*\d+\s*판|\d+차\s*개정판?|개정판?|재안내|안내|배포용|_?전자용|제정', ' ', t)
    return re.sub(r'[\s·‧,.\-_및]', '', t)


def latest_per_series(rows_, limit):
    """계열(제목에서 연도·판을 뺀 것)마다 최신판 하나만.
    지침 → 서식 → 교육홍보 순으로 놓고, 같은 종류 안에서는 최신 연도 순."""
    by = defaultdict(list)
    for r in rows_:
        if DOC_DROP.search(r['제목']):
            continue
        by[series_key(r['제목'])].append(r)
    out = []
    for k, rs in by.items():
        rs.sort(key=year_of, reverse=True)
        top = dict(rs[0])
        top['editions'] = len(rs)
        top['stale'] = year_of(rs[0]) < THIS_YEAR - 1   # 재작년 이전 판이 최신이면 신판 확인 필요
        top['kind'] = doc_kind(top['제목'])
        out.append(top)
    out.sort(key=lambda r: (KIND_RANK[r['kind']], -year_of(r)))
    return out[:limit]


def load_corrections():
    """손으로 적는 보정. 제목만으로 못 잡는 소속·게시판 밖 지침을 여기에 적는다.
    지침_보정.csv: 지침명, 다루는병(;로 구분), 계열, URL, 등록일, 비고"""
    p = os.path.join(ROOT, '02_지침_정리', 'data', '지침_보정.csv')
    if not os.path.exists(p):
        return [], {}
    extra_rows, extra_map = [], defaultdict(list)
    for r in csv.DictReader(open(p, encoding='utf-8-sig')):
        title = (r.get('지침명') or '').strip()
        if not title:
            continue
        row = {'제목': title, '등록일': (r.get('등록일') or '').strip(),
               'URL': (r.get('URL') or '').strip(), '출처': '보정', '비고': (r.get('비고') or '').strip()}
        extra_rows.append(row)
        for dz in re.split(r'[;,]', r.get('다루는병') or ''):
            dz = dz.strip()
            if dz:
                extra_map[dz].append(row)
    return extra_rows, extra_map


def build():
    os.makedirs(OUT, exist_ok=True)
    src = SRC if os.path.exists(SRC) else SRC_FALLBACK
    rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
    extra_rows, extra_map = load_corrections()
    rows += extra_rows
    diseases = load_diseases()
    aliases = load_aliases()

    # 묶음 지침 분류
    grouped = defaultdict(list)
    for r in rows:
        for g, pat in GROUP_PATTERNS:
            if re.search(pat, r['제목']):
                grouped[g].append(r)

    index, stats = [], {'direct': 0, 'group': 0, 'none': 0, 'stale': 0}
    for dz in diseases:
        ks = keys_for(dz, aliases)
        direct = []
        for r in rows:
            t = norm(r['제목'])
            if any(norm(k) in t for k in ks):
                direct.append(r)
        direct += extra_map.get(dz['name'], [])        # 손으로 적은 보정은 직접 연결로
        direct_latest = latest_per_series(direct, 6)   # 계열마다 최신판만

        gnames = [g for g, members in GROUP_MEMBERS.items() if dz['name'] in members]
        gcand = []
        for g in gnames:
            for r in latest_per_series(grouped.get(g, []), 2):
                gcand.append({'group': g, **r})
        # 전 질병 공통(진단검사·신고기준)
        for r in latest_per_series(grouped.get('진단검사', []), 1):
            gcand.append({'group': '진단검사', **r})

        def slim(r, kind, group=None):
            return {'title': r['제목'], 'date': r['등록일'], 'url': r['URL'],
                    'year': year_of(r), 'kind': kind, 'group': group,
                    'doc': r.get('kind', doc_kind(r['제목'])),
                    'editions': r.get('editions', 1), 'stale': bool(r.get('stale')),
                    'src': r.get('출처', ''), 'board': r.get('게시판', '')}

        entry = {
            'disease': dz['name'], 'grade': dz['grade'], 'icon': dz['icon'],
            'direct': [slim(r, 'direct') for r in direct_latest],
            'direct_total': len(direct),
            'group': [slim(r, 'group', r['group']) for r in gcand],
        }
        # 지금 펴야 할 지침 — direct/group을 가리지 않고 '지침' 종류 중 가장 최신.
        # 콜레라의 직접 지침은 2002년판뿐이라 2026년 수인성 지침이 정답이다.
        # 순서: (1) 현행판(재작년 이후)을 먼저 (2) 제목에 병명이 있는 것 (3) 관리·대응지침을
        # 사업지침·진료가이드보다 (4) 대상이 좁은 계열을 넓은 계열보다 (5) 최신 연도.
        # 두창은 2026년 진단검사 통합지침보다 2025년 제1급 대응지침이 정답이고,
        # A형간염은 수인성(12종)보다 간염(4종), 콜레라는 2002년 직접 지침보다 2026년 수인성이 정답이다.
        SPAN = {g: len(m) for g, m in GROUP_MEMBERS.items()}
        SPAN['진단검사'] = 999   # 전 질병 공통이라 가장 넓다

        def title_tier(t):
            if re.search(r'관리\s*지침|대응\s*지침|방역\s*지침|관리지침|대응지침', t):
                return 0
            if re.search(r'사업\s*지침|운영\s*지침|실시\s*기준|네트워크', t):
                return 2
            return 1

        def rank(x):
            return (1 if x['stale'] else 0, 0 if x['kind'] == 'direct' else 1,
                    title_tier(x['title']), SPAN.get(x.get('group'), 50), -x['year'])
        cands = sorted([x for x in entry['direct'] + entry['group'] if x['doc'] == '지침'], key=rank)
        entry['primary'] = cands[0] if cands else None
        if any(x['stale'] for x in entry['direct'] + entry['group']):
            stats['stale'] += 1
        index.append(entry)
        if direct:
            stats['direct'] += 1
        elif gcand:
            stats['group'] += 1
        else:
            stats['none'] += 1

    order = {'제1급': 1, '제2급': 2, '제3급': 3, '제4급': 4}
    index.sort(key=lambda e: (order.get(e['grade'], 9), e['disease']))

    meta = {
        'as_of': '2026-09',
        'source': ('질병관리청 누리집 지침 게시판(kdca.go.kr/bbs/kdca/55) 전량 + 감염병포털 게시판 358건, '
                   f'제목·연도로 통합 {len(rows)}건' if src == SRC else
                   '질병관리청 감염병포털 감염병지침 게시판 전량 크롤링(358건, 2002~2026)'),
        'levels': {
            'direct': '지침 제목에 그 질병명·옛 이름·약어가 들어 있다 — 사실',
            'group': '그 질병이 속한 계열의 묶음 지침 — 찾아볼 후보. '
                     '묶음 지침이 실제로 어느 질병을 다루는지는 원문 목차 확인이 필요하다',
        },
        'editions': '지침은 대개 매년 다시 낸다. 같은 계열은 최신판 하나만 보이고 판 수를 적는다. '
                    f'최신판이 {THIS_YEAR - 2}년 이전이면 stale — 신판이 있는지 게시판을 확인할 것.',
        'caution': "제목에 '(4종)'처럼 대상 수가 적힌 묶음 지침이 있다. 대상 목록은 원문에서 확인할 것.",
        'stats': dict(stats, total=len(index), guidelines=len(rows)),
    }
    json.dump({'meta': meta, 'index': index},
              open(os.path.join(OUT, '감염병별_지침색인.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    with open(os.path.join(OUT, '감염병별_지침색인.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['급', '감염병', '연결등급', '계열', '지침명', '등록일', 'URL'])
        for e in index:
            for r in e['direct']:
                w.writerow([e['grade'], e['disease'], 'direct', '', r['title'], r['date'], r['url']])
            for r in e['group']:
                w.writerow([e['grade'], e['disease'], 'group', r['group'], r['title'], r['date'], r['url']])

    print(f"지침 {len(rows)}건 → 질병 {len(index)}종")
    print(f"  제목에 병명이 직접 있는 질병: {stats['direct']}종")
    print(f"  계열 묶음 지침만 있는 질병: {stats['group']}종")
    print(f"  연결 지침 없음: {stats['none']}종")
    miss = [e['disease'] for e in index if not e['direct'] and not e['group']]
    if miss:
        print('  없음:', ', '.join(miss[:20]))
    return index, meta


if __name__ == '__main__':
    build()
