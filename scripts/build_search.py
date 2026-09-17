#!/usr/bin/env python3
"""통합검색 색인 조립 — 흩어진 페이지를 '감염병 하나'로 묶어 준다.

이 사이트의 가장 큰 불편은 같은 감염병 정보가 도감·현장카드·지침·연대기·예방접종에
따로 놓여 있고, 그 사이를 잇는 입구가 없다는 것이었다. 여기서는 원자료를 그대로 두고
읽기만 해서 색인 하나를 만든다. 어떤 페이지도 고치지 않는다.

산출
  portal/search/index.json  — 질병 묶음(hubs) + 낱개 기록(records)
  portal/search/index.html  — 색인을 읽어 보여주는 검색 페이지

기록마다 id·title·type·disease·year·source·url을 갖게 한다(지시서 32항). 나중에
'이 아카이브에 질문하기'를 붙일 때 원자료 링크와 함께 답할 수 있어야 하기 때문이다.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
OUTDIR = os.path.join(ROOT, 'portal', 'search')

# 출처 성격 — 지시서 12항의 세 갈래. 화면에서 배지로 구분한다.
OFFICIAL, ARCHIVE, ANALYSIS = 'official', 'archive', 'analysis'


def norm(s):
    """검색 대조용 — 공백·가운뎃점·괄호를 지우고 소문자로."""
    return re.sub(r'[\s·・()（）\[\]{}·,.\-/]', '', str(s or '')).lower()


# ── 1. 질병 묶음 ──────────────────────────────────────────────────────────
def disease_hubs():
    import build_dogam as bd
    alias_map, eng_map = bd.load_aliases()
    hubs = {}
    for gnum, glabel, fname, gdesc in bd.GRADES:
        parsed = bd.parse_file(os.path.join(bd.SRC, fname))
        if gnum == '4':
            parsed += bd.parse_resistant(os.path.join(bd.SRC, fname))
        for d in parsed:
            base = re.sub(r'\s*감염증$|\s*\(.*\)$', '', d['name'])
            als = alias_map.get(d['name']) or alias_map.get(base) or []
            eng = d['eng'] or eng_map.get(d['name'], '')
            f = dict(d['fields'])
            hubs[d['name']] = {
                'name': d['name'], 'eng': eng, 'alias': als, 'grade': gnum,
                'grade_label': glabel,
                'incub': f.get('잠복기', ''), 'route': f.get('전파경로', '') or f.get('감염경로', ''),
                'links': [], 'guides': 0,
            }
    return hubs


def add_link(hub, label, url, kind, note=''):
    hub['links'].append({'l': label, 'u': url, 'k': kind, 'n': note})


# ── 2. 각 축이 그 감염병에 대해 무엇을 갖고 있나 ──────────────────────────
def attach_field(hubs, records):
    """현장 대응카드 — 이미 조립된 페이지에서 읽는다(원본 빌드를 다시 돌리지 않는다)."""
    p = os.path.join(ROOT, 'portal', 'field', 'index.html')
    if not os.path.exists(p):
        return
    h = open(p, encoding='utf-8').read()
    m = re.search(r'const D = (\{.*?\});\n', h, re.S)
    if not m:
        return
    for c in json.loads(m.group(1)).get('cards', []):
        n = c['disease']
        hub = hubs.setdefault(n, {'name': n, 'eng': '', 'alias': [], 'grade': '', 'grade_label': '',
                                  'incub': '', 'route': '', 'links': [], 'guides': 0})
        if not hub.get('incub') and c.get('incub'):
            hub['incub'] = c['incub']
        if not hub.get('route') and c.get('route'):
            hub['route'] = c['route']
        if not hub.get('grade') and c.get('grade'):
            hub['grade_label'] = c['grade']
        bits = [x for x in (c.get('report') and f"신고 {c['report']}", c.get('iso')) if x]
        add_link(hub, '현장 대응카드', f"../field/#{n}", ARCHIVE, ' · '.join(bits))
        hub['guides'] = max(hub['guides'], c.get('guides_total') or 0)
        records.append({'t': f'{n} 현장 대응카드', 's': ' · '.join(bits) or '신고·격리·잠복기 한 화면',
                        'k': '현장', 'd': n, 'u': f'../field/#{n}', 'src': '질병관리청 지침 재구성', 'b': ARCHIVE})


def attach_pathogen(hubs):
    p = os.path.join(ROOT, 'portal', 'pathogen', 'index.html')
    if not os.path.exists(p):
        return
    h = open(p, encoding='utf-8').read()
    for n in hubs:
        if f'id="{n}"' in h:
            add_link(hubs[n], '병원체 형태', f'../pathogen/#{n}', ARCHIVE)


def attach_chronicle(hubs, records):
    p = os.path.join(ROOT, 'portal', 'data', 'files', '연대기.json')
    if not os.path.exists(p):
        return
    d = json.load(open(p, encoding='utf-8'))
    for dz in d.get('diseases', []):
        n = dz['name']
        hub = hubs.get(n)
        ph = [x for x in dz.get('phases', []) if x.get('status')]
        note = ''
        if len(ph) > 1:
            note = f"{ph[0]['status']} → {ph[-1]['status']} · 단계 {len(ph)}"
        if hub:
            add_link(hub, '연대기 (급수·감시 변천)', f"../chronicle/#{n}", ARCHIVE, note)
        records.append({'t': f'{n} 연대기', 's': note or '급수·감시체계 변천', 'k': '연대기', 'd': n,
                        'u': f'../chronicle/#{n}', 'src': '감염병예방법 원문 대조', 'b': ARCHIVE})


def attach_vaccine(hubs, records):
    p = os.path.join(ROOT, 'portal', 'data', 'files', '백신_감염병_연결.json')
    if not os.path.exists(p):
        return
    d = json.load(open(p, encoding='utf-8'))
    for v in d.get('vaccines', []):
        for n in v.get('diseases', []):
            if n in hubs:
                add_link(hubs[n], '예방접종', f"../vaccine/#{norm(v.get('code') or v.get('name'))}",
                         ARCHIVE, f"{v.get('name', '')} 백신")
        records.append({'t': f"{v.get('name', '')} ({v.get('code', '')}) 예방접종",
                        's': '어린이 접종률과 집단면역 임계치', 'k': '예방접종',
                        'd': (v.get('diseases') or [''])[0], 'u': '../vaccine/',
                        'src': '질병관리청 예방접종통계', 'b': ARCHIVE})


def attach_guides(hubs, records):
    p = os.path.join(ROOT, '02_지침_정리', 'data', '지침_통합목록.csv')
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    names = sorted(hubs, key=len, reverse=True)
    for r in rows:
        if r.get('최신판') != 'Y':
            continue
        title = r['제목']
        hit = next((n for n in names if len(n) >= 2 and n in title), '')
        if hit:
            hubs[hit]['guides'] = hubs[hit].get('guides', 0) or 0
        records.append({'t': title, 's': f"{r.get('등록일', '')} · {r.get('게시판', '')}"
                        + (f" · {r.get('판수', '')}판" if (r.get('판수') or '') not in ('', '1') else ''),
                        'k': '지침', 'd': hit, 'y': r.get('연도', ''),
                        'u': r.get('URL') or r.get('URL2') or '../guides/',
                        'src': '질병관리청 게시판', 'b': OFFICIAL, 'ext': 1})
    for n, hub in hubs.items():
        if hub.get('guides'):
            add_link(hub, '관리지침', f"../guides/#{n}", OFFICIAL, f"계열 {hub['guides']}건")


def attach_law(records):
    p = os.path.join(ROOT, 'portal', 'data', 'files', '감염병예방법_연혁_전체.csv')
    if not os.path.exists(p):
        return
    for r in csv.DictReader(open(p, encoding='utf-8-sig')):
        d = r.get('시행일자', '') or r.get('공포일자', '')
        y = d[:4]
        records.append({'t': f"{r.get('법령명', '')} {r.get('제개정구분', '')}",
                        's': f"시행 {d[:4]}.{d[4:6]}.{d[6:]} · 공포번호 {r.get('공포번호', '')}",
                        'k': '법령', 'y': y, 'u': '../law/', 'src': '국가법령정보센터', 'b': OFFICIAL})


def attach_whitepaper(records):
    p = os.path.join(ROOT, 'portal', 'data', 'files', '백서_목록.json')
    if not os.path.exists(p):
        return
    for it in json.load(open(p, encoding='utf-8')).get('items', []):
        m = re.search(r'(19|20)\d{2}', it.get('label', ''))
        records.append({'t': it.get('label', ''), 's': '질병관리청 백서', 'k': '백서',
                        'y': m.group(0) if m else '', 'u': '../whitepaper/',
                        'src': '질병관리청', 'b': OFFICIAL})


def attach_country(records):
    p = os.path.join(ROOT, 'portal', 'data', 'files', '국가별_유입_종합.csv')
    if not os.path.exists(p):
        return
    for r in csv.DictReader(open(p, encoding='utf-8')):
        ko = r.get('국가', '')
        if not ko:
            continue
        q = r.get('검역관리지역_종수') or '0'
        pri = r.get('중점_종수') or '0'
        bits = []
        if q != '0':
            bits.append(f'검역관리지역 {q}종')
        if pri != '0':
            bits.append(f'중점 {pri}종')
        if r.get('유입신고_건수'):
            bits.append(f"표본 유입 {r['유입신고_건수']}건")
        records.append({'t': ko, 's': ' · '.join(bits) or (r.get('지역') or ''), 'k': '국가',
                        'u': f"../inflow/#{r.get('ISO3', '')}", 'src': '질병관리청 · 국토부 · 법무부',
                        'b': ARCHIVE, 'x': r.get('ISO3', '')})


def attach_pages(records):
    import portal_tools as pt
    for gid, icon, label, items in pt.NAV_GROUPS:
        for href, name, desc in items:
            if '://' in href:
                continue
            records.append({'t': name, 's': f'{label} · {desc}', 'k': '페이지',
                            'u': '../' + href, 'src': '이 사이트', 'b': ARCHIVE})


# ── 3. 조립 ───────────────────────────────────────────────────────────────
def build():
    hubs = disease_hubs()
    records = []
    attach_field(hubs, records)
    attach_pathogen(hubs)
    attach_chronicle(hubs, records)
    attach_vaccine(hubs, records)
    attach_guides(hubs, records)
    attach_law(records)
    attach_whitepaper(records)
    attach_country(records)
    attach_pages(records)

    for n, hub in hubs.items():
        add_link(hub, '감염병 도감', f'../dogam/#{n}', ARCHIVE,
                 hub.get('grade_label') or (f"제{hub['grade']}급" if hub['grade'] else ''))
        hub['links'].sort(key=lambda x: ['감염병 도감', '현장 대응카드', '관리지침', '연대기',
                                         '예방접종', '병원체 형태'].index(x['l'])
                          if x['l'] in ['감염병 도감', '현장 대응카드', '관리지침', '연대기',
                                        '예방접종', '병원체 형태'] else 9)
        hub['q'] = norm(' '.join([n, hub['eng'], *hub['alias']]))

    # 대조용 문자열(q)은 저장하지 않는다 — 제목에서 바로 만들 수 있어 파일만 두 배가 된다.
    # 불러온 쪽에서 한 번 계산한다(2,000여 건이라 눈에 띄지 않는다).
    srcs = sorted({r.get('src', '') for r in records})
    si = {v: i for i, v in enumerate(srcs)}
    for r in records:
        r['src'] = si[r.get('src', '')]

    idx = {
        'as_of': __import__('datetime').date.today().isoformat(),
        'hubs': sorted(hubs.values(), key=lambda h: h['name']),
        'records': records,
        'srcs': srcs,
        'counts': {'질병': len(hubs), '기록': len(records)},
    }
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, 'index.json')
    json.dump(idx, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    tpl = os.path.join(ROOT, 'scripts', 'templates', 'search.template.html')
    html = open(tpl, encoding='utf-8').read().replace('__COUNTS__', json.dumps(idx['counts'], ensure_ascii=False))
    page = os.path.join(OUTDIR, 'index.html')
    open(page, 'w', encoding='utf-8').write(html)

    # 다른 페이지와 같은 머리글·메뉴·인쇄 도구를 붙인다
    try:
        from portal_tools import ensure_head, inject, inject_nav
    except ImportError:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        from portal_tools import ensure_head, inject, inject_nav
    ensure_head(page)
    inject(page, 1)
    inject_nav(page, 1, 'search')

    kinds = {}
    for r in records:
        kinds[r['k']] = kinds.get(r['k'], 0) + 1
    print(f"검색 색인 — 질병 {len(hubs)}종 · 기록 {len(records)}건 {kinds}")
    print(f"  → portal/search/index.json ({os.path.getsize(out):,}B)")


if __name__ == '__main__':
    build()
