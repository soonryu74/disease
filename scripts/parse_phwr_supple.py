#!/usr/bin/env python3
"""PHWR「주요 감염병 통계」PDF → 진단검사(병원체감시) 시계열 JSON.

주간 건강과 질병(Public Health Weekly Report) 부록의 병원체감시 표를 파싱한다.
각 호는 최근 4주치를 담으므로 4호 간격으로 모으면 전 주차를 덮는다.

## 판 사이 포맷 차이 (17권 vs 18·19권)
 - 17권(2024)은 장 번호에 전각 로마숫자(Ⅴ·Ⅵ)를 쓴다 → NFKC 정규화로 흡수.
 - 17권은 표 본문이 장 제목보다 **먼저** 추출된다 → 제목 기준으로 자르지 않고,
   **쪽 단위 + 열 머리글 서명**으로 표를 찾는다.
 - 17권 표에는 연도 칼럼이 없다 → 그 호의 기준 주차에서 연도를 추론한다.
 - 그래프 축 라벨이 숫자열로 오인될 수 있다 → 주차 1~53, 백분율 0~100 범위 검사로 거른다.
"""
import json
import re
import sys
import unicodedata

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
    return [unicodedata.normalize('NFKC', p.extract_text() or '') for p in r.pages]


def find_issue(texts):
    m = re.search(r'제\s*(\d+)\s*권\s*제\s*(\d+)\s*호\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', texts[0])
    if not m:
        return None
    v, n, y, mo, d = (int(x) for x in m.groups())
    return v, n, f'{y:04d}-{mo:02d}-{d:02d}'


def page_with(texts, *needles, exclude=()):
    """모든 needle을 담고 exclude는 담지 않는 첫 쪽의 텍스트."""
    for t in texts:
        flat = re.sub(r'\s+', '', t)
        if all(re.sub(r'\s+', '', n) in flat for n in needles) \
                and not any(re.sub(r'\s+', '', e) in flat for e in exclude):
            return t
    return ''


def ref_week(text, label):
    """'(38주차, 2024. 9. 21. 기준)' → (38, '2024-09-21')"""
    m = re.search(re.escape(label) + r'[^(]{0,40}\((\d+)\s*주차\s*,\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', text)
    if not m:
        m = re.search(r'\((\d+)\s*주차\s*,\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', text)
    if not m:
        return None, None
    return int(m.group(1)), f'{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}'


def year_for(week, base_week, base_year):
    """표에 연도 칼럼이 없을 때: 기준 주차보다 훨씬 큰 주차는 전년도."""
    if base_week is None or base_year is None:
        return None
    return base_year - 1 if week > base_week + 6 else base_year


# ── IV-1 인플루엔자 ──────────────────────────────────────────────────────
def parse_influenza(texts):
    t = page_with(texts, '인플루엔자 바이러스 주간 현황')
    if not t:
        return None
    out = {}
    w, asof = ref_week(t, '인플루엔자 바이러스 주간 현황')
    if w:
        out['week'], out['as_of'] = w, asof
    m = re.search(r'인플루엔자\s*양성률\s*[:：]\s*(' + NUM + r')\s*%', t)
    if m:
        out['positivity'] = to_f(m.group(1))
    m = re.search(r'A\(H1N1\)pdm09\s*(' + NUM + r')\s*%\s*,\s*A\(H3N2\)\s*(' + NUM +
                  r')\s*%\s*,\s*B\s*(' + NUM + r')\s*%', t)
    if m:
        out['H1N1pdm09'], out['H3N2'], out['B'] = (to_f(x) for x in m.groups())
    m = re.search(r'표본보고기관\s*[:：]\s*(\d+)\s*개\s*의료기관', t)
    if m:
        out['sentinel_clinics'] = int(m.group(1))
    return out or None


# ── IV-2 호흡기바이러스 ──────────────────────────────────────────────────
RESP_COLS = ['총검출률', '아데노', '보카', '파라인플루엔자', 'RSV', '리노',
             '메타뉴모', '코로나', '인플루엔자', '코로나19']


def parse_respiratory(texts):
    t = page_with(texts, '호흡기 바이러스 주간 현황')
    if not t:
        return []
    base_w, asof = ref_week(t, '호흡기 바이러스 주간 현황')
    base_y = int(asof[:4]) if asof else None
    rows, year = [], None
    for line in t.split('\n'):
        line = line.strip()
        m = re.match(r'^(?:(\d{4})\s+)?(\d{1,2})\s+((?:' + NUM + r'\s+){9}' + NUM + r')\s*$', line)
        if not m:
            continue
        if m.group(1):
            year = int(m.group(1))
        w = int(m.group(2))
        vals = [to_f(x) for x in m.group(3).split()]
        if len(vals) != 10 or not (1 <= w <= 53):
            continue
        if any(v is None or v < 0 or v > 100 for v in vals):
            continue          # 그래프 축 라벨 등 백분율이 아닌 숫자열을 거른다
        y = year if year is not None else year_for(w, base_w, base_y)
        if y is None:
            continue
        rows.append(dict(zip(['year', 'week'], [y, w]), **dict(zip(RESP_COLS, vals))))
    return dedup_weeks(rows)


# ── V 급성설사 바이러스 / 세균 ───────────────────────────────────────────
DIARV_COLS = ['노로', '그룹A로타', '장내아데노', '아스트로', '사포', '합계']
DIARB_COLS = ['살모넬라', '병원성대장균', '세균성이질', '장염비브리오', '비브리오콜레라',
              '캄필로박터', '클로스트리듐퍼프린젠스', '황색포도알균', '바실루스세레우스', '합계']


def parse_pair_table(texts, cols, needles, label, suffix, exclude=()):
    """'검체수 + (건수 (비율)) × N' 형태의 표. 쪽 단위로 찾는다."""
    t = page_with(texts, *needles, exclude=exclude)
    if not t:
        return []
    base_w, asof = ref_week(t, label)
    base_y = int(asof[:4]) if asof else None
    body = re.sub(r'\s*\n\s*', ' ', t)
    rows, year = [], None
    n = len(cols)
    # 열 수를 정확히 맞춘다 — 뒤에 짝이 더 오면 다른 표(예: 6열 바이러스 표가
    # 10열 세균 표의 앞부분을 잡는 일)이므로 매칭하지 않는다.
    pat = (r'(?:(\d{4})\s+)?(\d{1,2})\s+([\d,]+)\s+'
           r'((?:[\d,]+\s*\(\s*' + NUM + r'\s*\)\s*){' + str(n) + r'})'
           r'(?!\s*[\d,]+\s*\()')
    for m in re.finditer(pat, body):
        if m.group(1):
            year = int(m.group(1))
        w = int(m.group(2))
        if not (1 <= w <= 53):
            continue
        pairs = re.findall(r'([\d,]+)\s*\(\s*(' + NUM + r')\s*\)', m.group(4))
        if len(pairs) != n:
            continue
        pcts = [to_f(p) for _, p in pairs]
        if any(p is None or p < 0 or p > 100 for p in pcts):
            continue
        y = year if year is not None else year_for(w, base_w, base_y)
        if y is None:
            continue
        row = {'year': y, 'week': w, 'specimens': to_i(m.group(3))}
        for col, (cnt, pct) in zip(cols, pairs):
            row[col + '_건수'] = to_i(cnt)
            row[col + suffix] = to_f(pct)
        rows.append(row)
    return dedup_weeks(rows)


def dedup_weeks(rows):
    """같은 (연도,주차)가 여러 번 잡히면 마지막 것을 남긴다."""
    seen = {}
    for r in rows:
        seen[(r['year'], r['week'])] = r
    return [seen[k] for k in sorted(seen)]


def parse_diarrhea_virus(texts):
    return parse_pair_table(texts, DIARV_COLS,
                            ('노로바이러스', '사포바이러스'),
                            '급성설사 바이러스 주간 검출 현황', '_검출률')


def parse_diarrhea_bacteria(texts):
    return parse_pair_table(texts, DIARB_COLS,
                            ('살모넬라', '바실루스'),
                            '급성설사 세균 주간 검출 현황', '_분리율')


# ── VI 엔테로바이러스 ────────────────────────────────────────────────────
def parse_entero(texts):
    t = page_with(texts, '엔테로바이러스 주간 검출 현황')
    if not t:
        return None
    out = {}
    w, asof = ref_week(t, '엔테로바이러스 주간 검출 현황')
    if w:
        out['week'], out['as_of'] = w, asof
    flat = t.replace('\n', ' ')
    m = re.search(r'검출률\s*[:：]\s*(' + NUM + r')\s*%\s*\(\s*([\d,]+)건?\s*양성\s*/\s*([\d,]+)\s*검체', flat)
    if m:
        out['positivity'] = to_f(m.group(1))
        out['positive'] = to_i(m.group(2))
        out['specimens'] = to_i(m.group(3))
    for key, pat in (('무균성수막염', r'무균성수막염\s*[:：]\s*([\d,]+)\s*건'),
                     ('수족구병', r'수족구병\s*및\s*포진성구협염\s*[:：]\s*([\d,]+)\s*건'),
                     ('합병증동반수족구병', r'합병증\s*동반\s*수족구병\s*[:：]\s*([\d,]+)\s*건'),
                     ('기타', r'기타\s*[:：]\s*([\d,]+)\s*건')):
        m = re.search(pat, flat)
        if m:
            out[key] = to_i(m.group(1))
    return out or None


# ── 요약 지표 ────────────────────────────────────────────────────────────
def parse_headlines(texts):
    flat = '\n'.join(texts).replace('\n', ' ')
    out = {}
    for key, word in (('diar_virus', '급성설사\\s*바이러스'), ('diar_bacteria', '급성설사\\s*세균')):
        m = re.search(word + r'\s*검출률\s*[:：]\s*(' + NUM +
                      r')\s*%\s*\(\s*([\d,]+)건?\s*양성\s*/\s*([\d,]+)\s*검체', flat)
        if m:
            out[key] = {'rate': to_f(m.group(1)), 'positive': to_i(m.group(2)),
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
