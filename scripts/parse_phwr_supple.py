#!/usr/bin/env python3
"""PHWR「주요 감염병 통계」PDF → 진단검사(병원체감시) 시계열 CSV.

주간 건강과 질병(Public Health Weekly Report) 부록 PDF의
IV~VI장(병원체감시)과 VII~IX장(매개체감시)에서 검출률·분리율 표를 파싱한다.

각 호는 최근 4주치를 담으므로 4주 간격으로 수집하면 전 주차를 덮는다.
같은 주가 여러 호에 나오면 나중 호(확정치에 가까움)를 채택한다.

사용:
    python3 scripts/parse_phwr_supple.py <pdf...>   # 표준출력에 JSON
"""
import json
import re
import sys

from pypdf import PdfReader

NUM = r'-?[\d,]+(?:\.\d+)?'


def to_f(s):
    s = (s or '').replace(',', '').strip()
    if s in ('', '-', '–', '—'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_i(s):
    v = to_f(s)
    return int(v) if v is not None and v == int(v) else v


def pages_text(path):
    r = PdfReader(path)
    return [(p.extract_text() or '') for p in r.pages]


def find_issue(texts):
    """(volume, number, date) — 1쪽 머리글 '제19권 제34호 2026. 9. 3.'"""
    m = re.search(r'제\s*(\d+)\s*권\s*제\s*(\d+)\s*호\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', texts[0])
    if not m:
        return None
    v, n, y, mo, d = (int(x) for x in m.groups())
    return v, n, f'{y:04d}-{mo:02d}-{d:02d}'


def sec(texts, start_pat, end_pat=None):
    """장 제목부터 다음 장 제목 전까지의 텍스트."""
    joined = '\n'.join(texts)
    m = re.search(start_pat, joined)
    if not m:
        return ''
    rest = joined[m.start():]
    if end_pat:
        m2 = re.search(end_pat, rest[10:])
        if m2:
            return rest[:10 + m2.start()]
    return rest[:6000]


# ── IV-1 인플루엔자 -------------------------------------------------------
def parse_influenza(texts):
    s = sec(texts, r'IV\.\s*병원체감시', r'V\.\s*병원체감시')
    if not s:
        return None
    out = {}
    m = re.search(r'인플루엔자\s*바이러스\s*주간\s*현황\((\d+)주차,\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', s)
    if m:
        out['week'] = int(m.group(1))
        out['as_of'] = f'{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}'
    m = re.search(r'인플루엔자\s*양성률\s*[:：]\s*(' + NUM + r')\s*%', s)
    if m:
        out['positivity'] = to_f(m.group(1))
    m = re.search(r'A\(H1N1\)pdm09\s*(' + NUM + r')\s*%\s*,\s*A\(H3N2\)\s*(' + NUM +
                  r')\s*%\s*,\s*B\s*(' + NUM + r')\s*%', s)
    if m:
        out['H1N1pdm09'], out['H3N2'], out['B'] = (to_f(x) for x in m.groups())
    m = re.search(r'표본보고기관\s*[:：]\s*(\d+)\s*개\s*의료기관', s)
    if m:
        out['sentinel_clinics'] = int(m.group(1))
    return out or None


# ── IV-2 호흡기바이러스 ---------------------------------------------------
RESP_COLS = ['총검출률', '아데노', '보카', '파라인플루엔자', 'RSV', '리노',
             '메타뉴모', '코로나', '인플루엔자', '코로나19']


def parse_respiratory(texts):
    s = sec(texts, r'2\.\s*호흡기\s*바이러스\s*주간\s*현황', r'V\.\s*병원체감시')
    if not s:
        return []
    rows, year = [], None
    for line in s.split('\n'):
        line = line.strip()
        m = re.match(r'^(?:(\d{4})\s+)?(\d{1,2})\s+((?:' + NUM + r'\s+){8,}' + NUM + r')\s*$', line)
        if not m:
            continue
        if m.group(1):
            year = int(m.group(1))
        vals = [to_f(x) for x in m.group(3).split()]
        if len(vals) < 10 or year is None:
            continue
        rows.append(dict(zip(['year', 'week'], [year, int(m.group(2))]),
                         **dict(zip(RESP_COLS, vals[:10]))))
    return rows


# ── V-1 급성설사 바이러스 -------------------------------------------------
DIARV_COLS = ['노로', '그룹A로타', '장내아데노', '아스트로', '사포', '합계']


def parse_diarrhea_virus(texts):
    s = sec(texts, r'V\.\s*병원체감시', r'2\.\s*급성설사\s*세균')
    if not s:
        return []
    body = re.sub(r'\s*\n\s*', ' ', s)
    rows, year = [], None
    # "2026 31 70 2 (2.9) 1 (1.4) ..." 형태
    for m in re.finditer(
            r'(?:(\d{4})\s+)?(\d{1,2})\s+([\d,]+)\s+' +
            r'((?:[\d,]+\s*\(\s*' + NUM + r'\s*\)\s*){6})', body):
        if m.group(1):
            year = int(m.group(1))
        if year is None:
            continue
        pairs = re.findall(r'([\d,]+)\s*\(\s*(' + NUM + r')\s*\)', m.group(4))
        if len(pairs) < 6:
            continue
        row = {'year': year, 'week': int(m.group(2)), 'specimens': to_i(m.group(3))}
        for col, (cnt, pct) in zip(DIARV_COLS, pairs):
            row[col + '_건수'] = to_i(cnt)
            row[col + '_검출률'] = to_f(pct)
        rows.append(row)
    return rows


# ── V-2 급성설사 세균 -----------------------------------------------------
DIARB_COLS = ['살모넬라', '병원성대장균', '세균성이질', '장염비브리오', '비브리오콜레라',
              '캄필로박터', '클로스트리듐퍼프린젠스', '황색포도알균', '바실루스세레우스', '합계']


def parse_diarrhea_bacteria(texts):
    s = sec(texts, r'2\.\s*급성설사\s*세균\s*주간\s*검출\s*현황', r'VI\.\s*병원체감시')
    if not s:
        return []
    body = re.sub(r'\s*\n\s*', ' ', s)
    rows, year = [], None
    for m in re.finditer(
            r'(?:(\d{4})\s+)?(\d{1,2})\s+([\d,]+)\s+' +
            r'((?:[\d,]+\s*\(\s*' + NUM + r'\s*\)\s*){10})', body):
        if m.group(1):
            year = int(m.group(1))
        if year is None:
            continue
        pairs = re.findall(r'([\d,]+)\s*\(\s*(' + NUM + r')\s*\)', m.group(4))
        if len(pairs) < 10:
            continue
        row = {'year': year, 'week': int(m.group(2)), 'specimens': to_i(m.group(3))}
        for col, (cnt, pct) in zip(DIARB_COLS, pairs):
            row[col + '_건수'] = to_i(cnt)
            row[col + '_분리율'] = to_f(pct)
        rows.append(row)
    return rows


# ── VI 엔테로바이러스 -----------------------------------------------------
def parse_entero(texts):
    s = sec(texts, r'VI\.\s*병원체감시\s*[:：]\s*엔테로', r'VII\.')
    if not s:
        return None
    out = {}
    m = re.search(r'엔테로바이러스\s*주간\s*검출\s*현황\((\d+)주차,\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', s)
    if m:
        out['week'] = int(m.group(1))
        out['as_of'] = f'{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}'
    m = re.search(r'검출률\s*[:：]\s*(' + NUM + r')\s*%\s*\(\s*([\d,]+)\s*양성\s*/\s*([\d,]+)\s*검체',
                  s.replace('\n', ' '))
    if m:
        out['positivity'] = to_f(m.group(1))
        out['positive'] = to_i(m.group(2))
        out['specimens'] = to_i(m.group(3))
    flat = s.replace('\n', ' ')
    for key, pat in (('무균성수막염', r'무균성수막염\s*[:：]\s*([\d,]+)\s*건'),
                     ('수족구병', r'수족구병\s*및\s*포진성구협염\s*[:：]\s*([\d,]+)\s*건'),
                     ('합병증동반수족구병', r'합병증\s*동반\s*수족구병\s*[:：]\s*([\d,]+)\s*건'),
                     ('기타', r'기타\s*[:：]\s*([\d,]+)\s*건')):
        m = re.search(pat, flat)
        if m:
            out[key] = to_i(m.group(1))
    return out or None


# ── 요약 지표(설사 바이러스/세균 주간 헤드라인) ---------------------------
def parse_headlines(texts):
    flat = '\n'.join(texts).replace('\n', ' ')
    out = {}
    m = re.search(r'급성설사\s*바이러스\s*검출률\s*[:：]\s*(' + NUM +
                  r')\s*%\s*\(\s*([\d,]+)\s*양성\s*/\s*([\d,]+)\s*검체', flat)
    if m:
        out['diar_virus'] = {'rate': to_f(m.group(1)), 'positive': to_i(m.group(2)),
                             'specimens': to_i(m.group(3))}
    m = re.search(r'급성설사\s*세균\s*검출률\s*[:：]\s*(' + NUM +
                  r')\s*%\s*\(\s*([\d,]+)건?\s*양성\s*/\s*([\d,]+)\s*검체', flat)
    if m:
        out['diar_bacteria'] = {'rate': to_f(m.group(1)), 'positive': to_i(m.group(2)),
                                'specimens': to_i(m.group(3))}
    m = re.search(r'호흡기바이러스\s*양성률\s*[:：]\s*(' + NUM + r')\s*%', flat)
    if m:
        out['resp_positivity'] = to_f(m.group(1))
    return out


def parse_pdf(path):
    texts = pages_text(path)
    iss = find_issue(texts)
    return {
        'file': path.split('/')[-1],
        'volume': iss[0] if iss else None,
        'number': iss[1] if iss else None,
        'date': iss[2] if iss else None,
        'influenza': parse_influenza(texts),
        'respiratory': parse_respiratory(texts),
        'diarrhea_virus': parse_diarrhea_virus(texts),
        'diarrhea_bacteria': parse_diarrhea_bacteria(texts),
        'enterovirus': parse_entero(texts),
        'headlines': parse_headlines(texts),
    }


if __name__ == '__main__':
    res = [parse_pdf(p) for p in sys.argv[1:]]
    print(json.dumps(res, ensure_ascii=False, indent=1))
