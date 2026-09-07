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
SRC = os.path.join(ROOT, '02_지침_정리', 'data', '지침_전체목록_감염병포털.csv')
CHRON = os.path.join(ROOT, '09_감염병연대기', 'data', '연대기.json')
ALIAS = os.path.join(ROOT, '05_감염병_질병정보', '별칭사전.json')
OUT = os.path.join(ROOT, '14_역학조사_실무', 'data')

# 묶음 지침 → 어느 계열을 찾는 사람에게 보여줄지. 계열 소속은 아래 GROUP_MEMBERS로 정의하고,
# '이 지침이 그 질병을 실제로 다루는지'는 원문 확인 사항으로 남긴다.
GROUP_PATTERNS = [
    ('호흡기', r'호흡기감염병'),
    ('수인성', r'수인성|식품매개'),
    ('예방접종', r'예방접종대상|예방접종'),
    ('성매개', r'성매개감염병|성병'),
    ('의료관련', r'의료관련감염|항생제내성|내성균'),
    ('인수공통', r'인수공통'),
    ('매개체', r'매개체|모기|진드기'),
    ('1급', r'제1급감염병'),
    ('진단검사', r'진단검사 통합지침|진단.*신고 기준|신고범위'),
    ('위기대응', r'위기관리|위기대응|생물테러'),
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


def build():
    os.makedirs(OUT, exist_ok=True)
    rows = list(csv.DictReader(open(SRC, encoding='utf-8-sig')))
    diseases = load_diseases()
    aliases = load_aliases()

    # 묶음 지침 분류
    grouped = defaultdict(list)
    for r in rows:
        for g, pat in GROUP_PATTERNS:
            if re.search(pat, r['제목']):
                grouped[g].append(r)

    index, stats = [], {'direct': 0, 'group': 0, 'none': 0}
    for dz in diseases:
        ks = keys_for(dz, aliases)
        direct = []
        for r in rows:
            t = norm(r['제목'])
            if any(norm(k) in t for k in ks):
                direct.append(r)
        direct.sort(key=year_of, reverse=True)

        gnames = [g for g, members in GROUP_MEMBERS.items() if dz['name'] in members]
        gcand = []
        for g in gnames:
            best = sorted(grouped.get(g, []), key=year_of, reverse=True)[:2]
            for r in best:
                gcand.append({'group': g, **r})
        # 전 질병 공통(진단검사·신고기준)
        for r in sorted(grouped.get('진단검사', []), key=year_of, reverse=True)[:1]:
            gcand.append({'group': '진단검사', **r})

        def slim(r, kind, group=None):
            return {'title': r['제목'], 'date': r['등록일'], 'url': r['URL'],
                    'year': year_of(r), 'kind': kind, 'group': group}

        entry = {
            'disease': dz['name'], 'grade': dz['grade'], 'icon': dz['icon'],
            'direct': [slim(r, 'direct') for r in direct[:6]],
            'direct_total': len(direct),
            'group': [slim(r, 'group', r['group']) for r in gcand],
        }
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
        'source': '질병관리청 감염병포털 감염병지침 게시판 전량 크롤링(358건, 2002~2026)',
        'levels': {
            'direct': '지침 제목에 그 질병명·옛 이름·약어가 들어 있다 — 사실',
            'group': '그 질병이 속한 계열의 묶음 지침 — 찾아볼 후보. '
                     '묶음 지침이 실제로 어느 질병을 다루는지는 원문 목차 확인이 필요하다',
        },
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
