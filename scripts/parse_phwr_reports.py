#!/usr/bin/env python3
"""PHWR「주요 감염병 통계」PDF → 환자감시(신고) 시계열 JSON.

병원체감시(진단검사)를 뽑는 parse_phwr_supple.py의 짝. 이쪽은 **신고** 축이다.
 - I장  전수감시: 질병별 금주 신고수 · 연 누계 · 5년 주별 평균 · 연도별 확정치 · 해외유입 국가
 - II장 표본감시: 인플루엔자 ILI · 수족구병 · 안과감염병 의사환자분율, 성매개 보고기관당 신고수

두 축을 같은 주차에 나란히 놓으면 '신고가 늘었는데 검출은 그대로'인 구간을 찾을 수 있다.
그 구간의 증가는 유행이 아니라 신고 행태·제도 변화일 가능성이 크다.

사용: python3 scripts/parse_phwr_reports.py <pdf...> > out.json
"""
import json
import re
import sys
import unicodedata

from pypdf import PdfReader

VAL = r'(?:[\d,]+|-|–|—)'


def to_i(s):
    s = (s or '').strip().replace(',', '')
    if s in ('', '-', '–', '—'):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def to_f(s):
    s = (s or '').strip().replace(',', '')
    if s in ('', '-', '–', '—'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pages_text(path):
    r = PdfReader(path)
    return [unicodedata.normalize('NFKC', p.extract_text() or '') for p in r.pages]


def find_issue(texts):
    m = re.search(r'제\s*(\d+)\s*권\s*제\s*(\d+)\s*호\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', texts[0])
    if not m:
        return None, None, None
    v, n, y, mo, d = (int(x) for x in m.groups())
    return v, n, f'{y:04d}-{mo:02d}-{d:02d}'


# ── I. 전수감시 주간 신고 ────────────────────────────────────────────────
GRADE_RE = re.compile(r'^제([1-4])급감염병')
# 표가 아닌 줄(각주·머리글)에서 잘못 읽는 것을 막는 낱말
SKIP_WORDS = ('누계', '평균', '연간현황', '해외유입현황', '단위', '기준', '포함', '참조',
              '미포함', '산출', '집계', '통계', '주차 보고', '국가명', '신고수', '감염병‡', '금주')


def parse_notifiable(texts):
    """전수감시 표 → {'as_of', 'week', 'years': [...], 'rows': [...]}"""
    head = texts[0]
    m = re.search(r'(\d{4})년\s*(\d+)주차\s*보고\s*현황\s*\((\d{4})\.\s*(\d+)\.\s*(\d+)', head)
    if not m:
        return None
    year, week = int(m.group(1)), int(m.group(2))
    as_of = f'{int(m.group(3)):04d}-{int(m.group(4)):02d}-{int(m.group(5)):02d}'
    ym = re.search(r'((?:\d{4}\s+){4}\d{4})', head)
    years = [int(x) for x in ym.group(1).split()] if ym else []

    rows, grade, namebuf, seen = [], None, '', set()
    for pg in texts[:12]:
        # I-2 '지역별 보고 현황' 표는 숫자 모양이 같아 시·도명이 질병으로 잡힌다.
        # 전국 표(I-1)만 읽고 거기서 멈춘다.
        if '지역별' in re.sub(r'\s+', '', pg):
            break
        for raw in pg.split('\n'):
            line = raw.strip()
            if not line:
                namebuf = ''
                continue
            g = GRADE_RE.match(line)
            if g:
                grade = int(g.group(1))
                namebuf = ''
                continue
            m = re.match(r'^(.*?)\s+((?:' + VAL + r'\s+){2,7}' + VAL + r')(?:\s+(.*))?$', line)
            if not m:
                # 숫자가 없는 줄은 다음 줄로 이어지는 질병명일 수 있다
                if re.fullmatch(r'[가-힣A-Za-z0-9()·\s]{2,30}', line) and not any(
                        w in line for w in SKIP_WORDS):
                    namebuf = line.strip()
                else:
                    namebuf = ''
                continue
            name = (namebuf + ' ' + m.group(1)).strip() if namebuf else m.group(1).strip()
            namebuf = ''
            name = re.sub(r'[*†‡§]+', '', name).strip()
            if not name or any(w in name for w in SKIP_WORDS):
                continue
            if not re.search(r'[가-힣]', name) or len(name) > 40:
                continue
            vals = m.group(2).split()
            imported = (m.group(3) or '').strip()
            sub = name.startswith(('  ', '　')) or bool(re.match(r'^\s+', m.group(1)))
            # 금주·누계는 어느 호에서든 맨 앞 두 칸으로 위치가 고정된다.
            # 반면 신규 편입 질병(매독·엠폭스 등)은 5년 주별 평균 칸이 아예 비어 있어
            # 열 수가 8개보다 적게 추출된다 → 그 경우 뒤쪽 열은 매핑하지 않는다(추정 금지).
            full = len(vals) == 8
            row = {
                'grade': grade,
                'disease': re.sub(r'\s+', ' ', name),
                'week_count': to_i(vals[0]),
                'cum': to_i(vals[1]),
                'avg5w': to_f(vals[2]) if full else None,
                'by_year': ({str(y): to_i(v) for y, v in zip(years, vals[3:8])}
                            if full and years else {}),
                'sub': sub,
            }
            if not full:
                row['partial_columns'] = len(vals)
            if imported and re.search(r'[가-힣].*\(', imported):
                row['imported'] = parse_imported(imported)
            if row['disease'] in seen:
                continue
            seen.add(row['disease'])
            rows.append(row)
    if not rows:
        return None
    return {'year': year, 'week': week, 'as_of': as_of, 'years': years, 'rows': rows}


def parse_imported(s):
    """'베트남(1), 싱가포르(1)' → [{'country':'베트남','n':1}, ...]"""
    out = []
    for m in re.finditer(r'([가-힣A-Za-z][가-힣A-Za-z\s·]*?)\s*\(\s*(\d+)\s*\)', s):
        c = re.sub(r'\s+', '', m.group(1))
        if c and len(c) <= 20:
            out.append({'country': c, 'n': int(m.group(2))})
    return out


# ── II. 표본감시 ─────────────────────────────────────────────────────────
def one(pat, text, cast=to_f):
    m = re.search(pat, text)
    return cast(m.group(1)) if m else None


def parse_sentinel(texts):
    body = '\n'.join(texts[8:14])
    out = {}
    m = re.search(r'인플루엔자\s*주간\s*발생\s*현황\((\d+)주차,\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', body)
    if m:
        out['influenza'] = {
            'week': int(m.group(1)),
            'as_of': f'{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}',
            'ili': one(r'의사환자분율\(ILI\)\s*[:：]\s*([\d.]+)\s*명', body),
            'clinics': one(r'의사환자분율\(ILI\)[\s\S]{0,160}?표본보고기관\s*[:：]\s*(?:전국\s*)?(\d+)\s*개',
                           body, to_i),
            'threshold': one(r'유행기준은\s*([\d.]+)\s*명', body),
        }
    m = re.search(r'수족구병\s*발생\s*주간\s*현황\((\d+)주차,\s*(\d{4})\.\s*(\d+)\.\s*(\d+)', body)
    if m:
        seg = body[m.start():m.start() + 400]
        out['hfmd'] = {
            'week': int(m.group(1)),
            'as_of': f'{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}',
            'rate': one(r'의사환자분율\s*[:：]\s*([\d.]+)\s*명', seg),
            'clinics': one(r'표본보고기관\s*[:：]\s*(?:전국\s*)?(\d+)\s*개', seg, to_i),
        }
    m = re.search(r'안과\s*감염병\s*주간\s*발생\s*현황\((\d+)주차', body)
    if m:
        seg = body[m.start():m.start() + 900]
        out['eye'] = {
            'week': int(m.group(1)),
            'keratoconjunctivitis': one(r'유행성각결막염\s*의사환자분율\s*[:：]\s*([\d.]+)\s*명', seg),
            'hemorrhagic': one(r'급성출혈성결막염\s*의사환자분율\s*[:：]\s*([\d.]+)\s*명', seg),
        }
    m = re.search(r'성매개감염병\s*주간\s*발생\s*현황\((\d+)주차', body)
    if m:
        seg = body[m.start():m.start() + 900].replace('\n', ' ')
        sti = {}
        for name in ('사람유두종바이러스 감염증', '성기단순포진', '첨규콘딜롬',
                     '클라미디아 감염증', '임질'):
            loose = r'\s*'.join(re.escape(c) for c in name.replace(' ', ''))
            mm = re.search(loose + r'\s*([\d.]+)\s*건', seg)
            if mm:
                sti[name] = to_f(mm.group(1))
        if sti:
            out['sti'] = {'week': int(m.group(1)), 'per_clinic': sti}
    return out or None


def parse_outbreak(texts):
    body = '\n'.join(texts[10:14]).replace('\n', ' ')
    m = re.search(r'집단발생\s*[:：]\s*([\d,]+)\s*건\s*,\s*([\d,]+)\s*명'
                  r'\s*\(금년\s*누적\s*발생\s*[:：]\s*([\d,]+)\s*건\s*,\s*([\d,]+)\s*명', body)
    if not m:
        return None
    w = re.search(r'집단발생\s*주간\s*현황\((\d+)주차', '\n'.join(texts[10:14]))
    return {'week': int(w.group(1)) if w else None,
            'events': to_i(m.group(1)), 'cases': to_i(m.group(2)),
            'cum_events': to_i(m.group(3)), 'cum_cases': to_i(m.group(4))}


def parse_pdf(path):
    texts = pages_text(path)
    v, n, d = find_issue(texts)
    return {'file': path.split('/')[-1], 'volume': v, 'number': n, 'date': d,
            'notifiable': parse_notifiable(texts),
            'sentinel': parse_sentinel(texts),
            'waterborne_outbreak': parse_outbreak(texts)}


if __name__ == '__main__':
    print(json.dumps([parse_pdf(p) for p in sys.argv[1:]], ensure_ascii=False, indent=1))
