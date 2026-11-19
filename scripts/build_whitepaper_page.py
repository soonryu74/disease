#!/usr/bin/env python3
"""③ 백서 서가 — 질병관리청 백서 2004~2024년 19판을 한 쪽에

여태 이 자료는 GitHub의 마크다운으로만 열렸다. 백서는 '읽는 물건'이므로
표지가 보이고, 어느 판을 내려받을 수 있고 어느 판이 사라졌는지가 한눈에 보여야 한다.

이 쪽이 말하는 것은 목록이 아니라 두 가지다.
 1. **9판이 사라졌다** — 2004~2011·2014~2015. 표지는 서버에 살아 있는데 본문 PDF가 없다.
    그 구간에 신종플루(2009)·결핵 정점(2011)·메르스(2015)가 통째로 들어 있다.
 2. **2024년판 숫자는 그대로 읽으면 틀린다** — 제2급 560만→15만은 방역 성과가 아니라
    코로나19의 4급 전환이다. 코로나를 빼면 오히려 +64.7%다.

산출: portal/whitepaper/index.html
"""
import csv
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D03 = os.path.join(ROOT, '03_백서_정리', 'data')
LIST = os.path.join(D03, '백서_목록.json')
NOTI = os.path.join(D03, '전수감시_신고수_2016_2025.csv')
SENT = os.path.join(D03, '표본감시_기관수_2001_2025.csv')
TPL = os.path.join(ROOT, 'scripts', 'templates', 'whitepaper.template.html')
OUT = os.path.join(ROOT, 'portal', 'whitepaper', 'index.html')

# 판마다 '그 해에 무슨 일이 있었나'. 백서 본문·보도자료에서 확인한 것만 적는다.
NOTES = {
    '2004': ('질병관리본부 설립 첫해(2004.1.1). 사스(2003) 직후 방역체계를 세우던 시기.', ''),
    '2005': ('설립 초기 감시·검역 체계 정비.', ''),
    '2006': ('KONIS(전국의료관련감염감시체계) 운영 시작 연도.', ''),
    '2007': ('', ''),
    '2008': ('', ''),
    '2009': ('신종인플루엔자 A(H1N1pdm09) 대유행. 국내 발생률 10만 명당 1,502.6명 — '
             '2020년 이전 최대 감염병 사건의 1차 사료다.', '⭐'),
    '2010': ('신종플루 유행 종료와 사후 정비.', ''),
    '2011': ('결핵 신고 최고치 50,491명(10만 명당 100.8명). 이후 13년 연속 감소의 기준점.', '⭐'),
    '2012': ('2009 신종플루 이후 위기대응 체계 정비, 국가예방접종·만성질환 감시.', ''),
    '2013': ('감염병 감시·검역, 국가예방접종 확대, 만성질환·건강조사.', ''),
    '2014~2015': ('메르스 유행(확진 186·사망 38) 당해를 수록하는 합본. '
                  '2016년판이 회고하지만 당해 기록과 사후 회고는 사료로서 값이 다르다.', '⭐'),
    '2016': ('2015 메르스 대응과 국가방역체계 개편.', ''),
    '2017': ('메르스 이후 긴급상황실 상시체계, 지카 대응.', ''),
    '2018': ('메르스 해외유입 1건(쿠웨이트) 조기 차단, 감시·검역 강화.', ''),
    '2019': ('상시 대응·예방접종·만성질환. 코로나19 직전 연도의 평시 기록.', ''),
    '2020~2021': ('코로나19 초기·확산 대응과 2020.9.12 질병관리청 승격, 중앙방역대책본부 구축.', '⭐'),
    '2022': ('오미크론 대유행, 단계적 일상회복, 백신·치료제.', ''),
    '2023': ('엔데믹 전환(위기단계 하향), 상시 관리체계 복귀. 2023.8.31 코로나19 제4급 전환.', ''),
    '2024': ('코로나19 마무리와 신종인플루엔자 대비. 제2차 말라리아 재퇴치 실행계획. '
             '텍스트 대체자료(txt)를 제공한 첫 판이라 본문 전량을 읽을 수 있다.', '⭐'),
}
# 발간기관 변천: 2020.9.11까지 질병관리본부 → 승격 후 질병관리청
KDCA_FROM = 2020


def editions():
    j = json.load(open(LIST, encoding='utf-8'))
    by = {}
    for it in j['items']:
        m = re.match(r'(\d{4}(?:~\d{4})?)년\s*(.*)', it['label'])
        if not m:
            continue
        y, rest = m.group(1), m.group(2)
        kind = '국문'
        if '[영문]' in rest:
            kind = '영문'
        elif '[텍스트]' in rest:
            kind = '텍스트'
        e = by.setdefault(y, {'y': y, 'hidden': it['hidden'], 'cover': '', 'files': [],
                              'org': '질병관리청' if int(y[:4]) >= KDCA_FROM else '질병관리본부'})
        if kind == '국문':
            # 표지는 저장소에 받아 둔 사본을 쓴다. 유실 9판은 이 그림이 유일한 흔적이다.
            e['cover'] = 'covers/' + it['cover_file'] if it.get('cover_file') else it['cover']
            e['hidden'] = it['hidden']
            e['cover_ok'] = it.get('cover_status', 200) in (200, 206)
        if it['file']:
            e['files'].append({'k': kind, 'u': it['file'],
                               'bad': it['file'] in j.get('mislinked', {}) and kind == '영문' and y == '2022'})
    out = []
    for y, e in sorted(by.items(), key=lambda kv: kv[0], reverse=True):
        note, star = NOTES.get(y, ('', ''))
        e['note'], e['star'] = note, star
        e['name'] = ('질병관리청 백서' if int(y[:4]) >= KDCA_FROM else '질병관리백서') + \
                    ('(합본)' if '~' in y else '')
        out.append(e)
    return out, j


def series_notifiable():
    """제2급 신고수 — 코로나19를 넣은 것과 뺀 것. 이 쪽에서 가장 중요한 그림이다."""
    rows = list(csv.DictReader(open(NOTI, encoding='utf-8-sig')))
    years = [str(y) for y in range(2016, 2026)]

    def total(pred):
        out = []
        for y in years:
            s = 0
            for r in rows:
                if not pred(r):
                    continue
                v = r[y].replace(',', '').strip()
                if v.isdigit():
                    s += int(v)
            out.append(s)
        return out
    g2 = lambda r: r['급'] == '제2급'                                    # noqa: E731
    return {
        'years': [int(y) for y in years],
        'all': total(g2),
        'no_covid': total(lambda r: g2(r) and '코로나' not in r['감염병명']),
        'g3': total(lambda r: r['급'] == '제3급'),
        'g3_no_syph': total(lambda r: r['급'] == '제3급' and '매독' not in r['감염병명']),
    }


def series_sentinel():
    """표본감시 기관수 — 분모다. 이게 바뀐 해를 모르고 신고수를 이으면 틀린다."""
    rows = list(csv.DictReader(open(SENT, encoding='utf-8-sig')))
    years = [str(y) for y in range(2000, 2026)]
    out = []
    for r in rows:
        vals = []
        for y in years:
            v = (r.get(y) or '').replace(',', '').strip()
            vals.append(int(v) if v.isdigit() else None)
        note = (r.get('지정기준 변경·비고') or '').strip()
        # 분모가 크게 흔들린 감시군만 그린다 — 최대·최소가 2배 넘게 벌어진 것
        got = [v for v in vals if v]
        if not got or max(got) < 2 * min(got):
            continue
        out.append({'n': r['감시군'], 'v': vals, 'note': note})
    return {'years': [int(y) for y in years], 'groups': out}


def build():
    eds, raw = editions()
    data = {
        'as_of': raw['as_of'],
        'source': raw['source'],
        'editions': eds,
        'hidden': sum(1 for e in eds if e['hidden']),
        'downloadable': sum(1 for e in eds if e['files']),
        'mislinked': raw.get('mislinked', {}),
        'noti': series_notifiable(),
        'sent': series_sentinel(),
    }
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = open(TPL, encoding='utf-8').read().replace('__DATA__', js)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)
    src = os.path.join(D03, 'covers')
    if os.path.isdir(src):
        dst = os.path.join(os.path.dirname(OUT), 'covers')
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
    n2 = data['noti']
    print(f'백서 서가 — {len(eds)}판 (내려받기 {data["downloadable"]} · 원문 유실 {data["hidden"]})')
    print(f'  제2급 2023 {n2["all"][7]:,} → 2024 {n2["all"][8]:,} '
          f'(코로나 제외 {n2["no_covid"][7]:,} → {n2["no_covid"][8]:,})')
    print(f'  분모가 흔들린 표본감시군 {len(data["sent"]["groups"])}개')
    print(f'  → {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,}B)')


if __name__ == '__main__':
    build()
