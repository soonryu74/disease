#!/usr/bin/env python3
"""⑱ 예방접종 — 「전국 어린이 예방접종률 현황」 전량 수집

질병관리청 예방접종도우미(nip.kdca.go.kr)가 해마다 7월에 공표하는 자료다.
게시판에는 PDF만 걸린 것처럼 보이지만, 본문 HTML에 백신별·연령별 표가 그대로 들어 있다.
PDF를 긁을 필요가 없다.

주의 — 이 서버는 TLS 재협상이 옛 방식이라 요즘 OpenSSL 기본 설정으로는 손이 닿지 않는다
(unsafe legacy renegotiation disabled). 인증서 검증은 그대로 두고 재협상만 허용하는
설정 파일을 만들어 curl에 붙인다. 검증을 끄는 것이 아니다.

산출
  18_예방접종/data/어린이_예방접종률.csv    연도 × 연령 × 백신 (접종자수·접종률)
  18_예방접종/data/어린이_예방접종률.json   위와 같은 자료 + 수집 메타
"""
import csv
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '18_예방접종', 'data')
BASE = 'https://nip.kdca.go.kr'
LIST = BASE + '/irhp/infm/goVcntInfo.do?menuLv=1&menuCd=165'
VIEW = BASE + '/irhp/infm/goNatnVcntStatView.do'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

OSSL = """openssl_conf = default_conf
[default_conf]
ssl_conf = ssl_sect
[ssl_sect]
system_default = sysdef
[sysdef]
Options = UnsafeLegacyRenegotiation
CipherString = DEFAULT:@SECLEVEL=1
"""

_tmp = tempfile.mkdtemp(prefix='nip_')
_cnf = os.path.join(_tmp, 'openssl.cnf')
open(_cnf, 'w').write(OSSL)
COOKIES = os.path.join(_tmp, 'cookies')
ENV = dict(os.environ, OPENSSL_CONF=_cnf)


def curl(url, post=None, tries=6):
    for i in range(tries):
        cmd = ['curl', '-sS', '-m', '90', '-A', UA, '-b', COOKIES, '-c', COOKIES]
        for k, v in (post or {}).items():
            cmd += ['--data-urlencode', f'{k}={v}']
        p = subprocess.run(cmd + [url], capture_output=True, text=True, env=ENV)
        if p.stdout and len(p.stdout) > 5000:
            return p.stdout
        time.sleep(2 + i * 3)
    return ''


def csrf_of(h):
    m = re.search(r'name="_csrf" value="([^"]+)"', h)
    return m.group(1) if m else ''


def cells(row):
    """한 줄의 칸을 글자만 남겨 뽑는다. rowspan 값도 함께."""
    out = []
    for m in re.finditer(r'<(t[hd])([^>]*)>([\s\S]*?)</\1>', row):
        txt = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(3)))
        rs = re.search(r'rowspan="(\d+)"', m.group(2))
        out.append((re.sub(r'\s+', ' ', txt).strip(), int(rs.group(1)) if rs else 1))
    return out


# 해마다 표 모양이 바뀐다. 2025년판은 머리글이 두 줄(질병명 / 백신 약어)이고,
# 2018~2024년판은 한 줄에 'BCG 결핵'처럼 붙어 있다. 약어만 뽑아 열 이름으로 삼는다.
VACC = ['BCG', 'HepB', 'Tdap', 'Td', 'DTaP', 'IPV', 'Hib', 'PCV', 'RV', 'MMR', 'VAR', 'HepA', 'JE']
VNORM = {v.lower(): v for v in VACC}
AGE = {'12': '1세', '24': '2세', '36': '3세', '72': '6세'}


def col_name(text):
    t = text.replace(' ', '')
    if '완전' in t:
        return '완전접종률'
    if t.startswith('구분') or not t:
        return ''
    m = re.match(r'([A-Za-z]+)', text.strip())
    if not m:
        return ''
    v = VNORM.get(m.group(1).lower())
    return v or ''


def norm_age(label):
    m = re.search(r'생후\s*(\d+)\s*개월', label)
    if m:
        return AGE.get(m.group(1), label)
    m = re.search(r'(\d+)\s*세', label)
    return f'{m.group(1)}세' if m else label


def parse_rates(page, year):
    """백신별·연령시기별 예방접종률 표 → 행 목록"""
    tab = None
    for t in re.findall(r'<table[\s\S]*?</table>', page):
        cap = re.search(r'<caption[^>]*>([\s\S]*?)</caption>', t)
        if cap and '예방접종률' in re.sub(r'<[^>]+>', '', cap.group(1)):
            tab = t
            break
    if tab is None:
        return []
    head = re.search(r'<thead>([\s\S]*?)</thead>', tab)
    body = re.search(r'<tbody>([\s\S]*?)</tbody>', tab)
    if not head or not body:
        return []
    hrows = re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', head.group(1))
    if not hrows:
        return []
    # 열 이름은 마지막 머리글 줄에서 뽑는다(두 줄이면 약어가 아랫줄에 있다).
    cols = [col_name(c) for c, _ in cells(hrows[-1])]
    cols = [c for c in cols if c]
    # '완전접종률'이 위쪽 줄에만 있는 판(rowspan=2)에서는 뒤에 붙인다.
    if '완전접종률' not in cols and any(
            '완전' in c.replace(' ', '') for r in hrows[:-1] for c, _ in cells(r)):
        cols.append('완전접종률')
    if len(cols) < 3:
        return []

    rows, age = [], ''
    for r in re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', body.group(1)):
        cs = cells(r)
        if not cs:
            continue
        if cs[0][1] > 1 or re.search(r'\d+\s*세|생후\s*\d+', cs[0][0]):
            age = cs[0][0]
            cs = cs[1:]
        kind = cs[0][0].replace(' ', '') if cs else ''
        vals = [c for c, _ in cs[1:]]
        if not kind.startswith('접종자') and not kind.startswith('접종률'):
            continue
        for name, v in zip(cols, vals):
            v = v.replace(',', '').strip()
            if v in ('', '-', '–', '·'):
                continue
            try:
                num = float(v)
            except ValueError:
                continue
            rows.append({'연도': year, '연령': norm_age(age),
                         '출생연도': (re.search(r'\((\d{4})년\s*생\)', age) or [None, ''])[1],
                         '백신': name, '항목': '접종자' if kind.startswith('접종자') else '접종률',
                         '값': num})
    return rows


def main():
    h = curl(LIST)
    if not h:
        sys.exit('예방접종도우미 목록을 못 받았다. 기존 파일을 지우지 않는다.')
    entries = [(n, html.unescape(t).strip())
               for n, t in re.findall(r"fnGoView\('(\d+)'\);\">([^<]+)</a>", h)]
    if not entries:
        sys.exit('목록 구조가 바뀌었다.')
    print(f'게시글 {len(entries)}건 — {entries[0][1]} … {entries[-1][1]}')
    token = csrf_of(h)

    all_rows, seen, skipped = [], [], []
    for n, title in entries:
        y = re.search(r'(20\d{2})년', title)
        if not y:
            skipped.append({'title': title, 'why': '연도별 정기 공표가 아니다'})
            print(f'  건너뜀 — {title}')
            continue
        year = int(y.group(1))
        # 한 세션 안에서는 토큰이 계속 통한다. 안 통할 때만 목록을 다시 받아 새로 얻는다.
        v = curl(VIEW, {'menuLv': '1', 'menuCd': '165', '_csrf': token, 'notSeqnum': n})
        rows = parse_rates(v, year)
        if not rows and '_csrf' not in v:
            token = csrf_of(curl(LIST)) or token
            v = curl(VIEW, {'menuLv': '1', 'menuCd': '165', '_csrf': token, 'notSeqnum': n})
            rows = parse_rates(v, year)
        if not rows:
            # 2016년 이전 판은 '연령 × 백신' 표가 아예 없다. 백신별 전체 접종률(2016),
            # 접종 시리즈별 완전접종률(2015), 백신 회차별 접종률(2013)로 각각 다른 것을
            # 센다. 억지로 이으면 없는 시계열을 만드는 것이므로 담지 않고 이유를 적는다.
            caps = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip()
                    for c in re.findall(r'<caption[^>]*>([\s\S]*?)</caption>', v)]
            skipped.append({'title': title, 'year': year,
                            'why': "'연령 × 백신' 표가 없다 — 이 판이 세는 것이 다르다",
                            'tables': caps})
            print(f'  담지 않음 {year}년 — 표 구성이 다르다: {" / ".join(caps)[:90]}')
            continue
        ages = sorted({r['연령'] for r in rows}, key=lambda s: int(re.sub(r'\D', '', s) or 0))
        vacc = sorted({r['백신'] for r in rows})
        print(f'  {year}년 {len(rows):4d}칸 · 연령 {"·".join(ages)} · 백신 {len(vacc)}종')
        all_rows += rows
        seen.append({'year': year, 'title': title, 'ages': ages, 'vaccines': vacc})

    if len(seen) < 5:
        sys.exit(f'해독한 해가 너무 적다({len(seen)}). 기존 파일을 지우지 않는다.')

    # 원문 오타를 지우지 않고 표시만 한다. 2024년판 6세 IPV 접종자가 '316,1823'으로
    # 적혀 있다 — 한 해 출생아가 25만 안팎이니 316만은 있을 수 없는 수다.
    anomalies = []
    for r in all_rows:
        bad = ('접종률이 100을 넘는다' if r['항목'] == '접종률' and r['값'] > 100
               else '접종자 수가 한 해 출생아보다 크다' if r['항목'] == '접종자' and r['값'] > 1_000_000
               else '')
        if bad:
            r['이상'] = bad
            anomalies.append(dict(r))
    for a in anomalies:
        print(f"  ⚠️ 원문 이상값 — {a['연도']} {a['연령']} {a['백신']} {a['항목']} {a['값']:,.0f} : {a['이상']}")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, '어린이_예방접종률.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['연도', '연령', '출생연도', '백신', '항목', '값', '이상'],
                           extrasaction='ignore', restval='')
        w.writeheader()
        w.writerows(sorted(all_rows, key=lambda r: (-r['연도'], r['연령'], r['백신'])))
    json.dump({'as_of': time.strftime('%Y-%m-%d'), 'source': LIST,
               'years': sorted({s['year'] for s in seen}), 'editions': seen,
               'anomalies': anomalies, 'skipped': skipped, 'rows': all_rows},
              open(os.path.join(OUT, '어린이_예방접종률.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'→ {len(all_rows):,}칸 · {len(seen)}개 연도 · {os.path.relpath(OUT, ROOT)}')


if __name__ == '__main__':
    main()
