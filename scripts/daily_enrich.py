#!/usr/bin/env python3
"""상황판 항목 살 붙이기 — 링크만 있던 항목에 '누르지 않아도 알 수 있는 것'을 단다.

무엇을 하는가
 - 한글 요약(ko): 원문에서 병명·나라·숫자·기준일·위험 평가·여행 제한 권고를 뽑아 틀에 맞춰 쓴다.
   문장을 번역하는 것이 아니다. 뽑은 사실만 한글로 적고, 못 뽑은 것은 비워 둔다.
 - 사실(facts): 확진·사망·치명률·기준일·위험도·단계처럼 숫자로 남는 것.
 - 원문 핵심(en): 영어 핵심 문장 두어 개. 화면에서 용어 사전(daily_glossary)으로 낱말마다 한글을 단다.
 - 그림(figs)·표(tables): WHO 질병 발생 뉴스 본문의 그림(발생 곡선·지도)과 표를 그대로 싣는다.

출처마다 뽑을 수 있는 것이 다르다.
 - WHO DON     API가 요약·개요·역학·위험 평가·권고를 절로 나눠 준다. 가장 풍부하다.
 - CDC 여행알림  알림 쪽에서 'Key points'와 지도를 가져온다. 단계(Level)는 뜻을 한글로 옮긴다.
 - CDC 발생조사  RSS 설명뿐이다(본문 주소가 내려받기 중계라 열리지 않는다). 숫자만 뽑는다.
 - KDCA 지침    글이 이미 한글이다. 담당부서·첨부 파일명·안내 문장을 뽑는다.

여기서 뽑은 것은 '원문에 이렇게 적혀 있다'이지 이 저장소의 판단이 아니다.
"""
import html
import re

from daily_glossary import GLOSSARY, LEVEL, MONTHS, RISK

ENRICH_V = 2
TERMS_SORTED = sorted(GLOSSARY.items(), key=lambda kv: -len(kv[0]))


def strip(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def sentences(text, n=2, cap=620):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    out = ' '.join(parts[:n]).strip()
    return out[:cap].rstrip() + ('…' if len(out) > cap else '')


def num(s):
    return int(s.replace(',', '').replace(' ', ''))


def parse_asof(text):
    """'As of 7 September 2026' → '2026-09-07'"""
    m = re.search(r'[Aa]s of (\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', text)
    if not m or m.group(2).lower() not in MONTHS:
        return ''
    return f'{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'


def find_terms(text, cap=14):
    """원문 영어에서 사전에 있는 낱말을 찾는다. 긴 표현부터, 낱말 경계로."""
    if not text:
        return []
    low = text.lower()
    used, out = [], []
    for en, ko in TERMS_SORTED:
        for m in re.finditer(r'(?<![a-z])' + re.escape(en) + r'(?![a-z])', low):
            a, b = m.start(), m.end()
            if any(a < ub and b > ua for ua, ub in used):
                continue
            used.append((a, b))
            out.append([text[a:b], ko])
            break
        if len(out) >= cap:
            break
    return out


# ── 그림·표 ─────────────────────────────────────────────────────────
def figures(html_body, cap=4):
    """<img> 마다 바로 앞의 'Figure N.' 문장을 설명으로 붙인다. 없으면 alt."""
    figs = []
    for m in re.finditer(r'<img[^>]*>', html_body or ''):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        if not src or not src.group(1).startswith('http'):
            continue
        alt = re.search(r'alt="([^"]*)"', tag)
        before = strip(html_body[max(0, m.start() - 420):m.start()])
        cap_m = re.search(r'((?:Figure|Fig\.|Map|Table)\s*\d+[.:].*)$', before)
        caption = cap_m.group(1).strip() if cap_m else (html.unescape(alt.group(1)) if alt and alt.group(1) else '')
        if any(f['src'] == src.group(1) for f in figs):
            continue
        figs.append({'src': src.group(1), 'caption': caption[:220]})
        if len(figs) >= cap:
            break
    return figs


def tables(html_body, cap=2, rows_cap=14, cols_cap=8):
    out = []
    for t in re.findall(r'<table[\s\S]*?</table>', html_body or '')[:cap]:
        rows = []
        for tr in re.findall(r'<tr[\s\S]*?</tr>', t):
            cells = [strip(c)[:60] for c in re.findall(r'<t[hd][^>]*>([\s\S]*?)</t[hd]>', tr)]
            if any(cells):
                rows.append(cells[:cols_cap])
            if len(rows) >= rows_cap:
                break
        if len(rows) >= 2:
            cap_m = re.search(r'<caption[^>]*>([\s\S]*?)</caption>', t)
            out.append({'caption': strip(cap_m.group(1))[:160] if cap_m else '', 'rows': rows})
    return out


# ── 출처별 ───────────────────────────────────────────────────────────
def _dz_ko_en(item):
    ko = (item.get('diseases') or [''])[0]
    title = item.get('title') or ''
    en = re.split(r'\s+[-–—]\s+', title)[0].strip()
    return ko, en


def _country_ko(item, ko_country):
    title = item.get('title') or ''
    parts = re.split(r'\s+[-–—]\s+', title)
    en = parts[-1].strip() if len(parts) > 1 else ''
    joins = [j['ko'] for j in item.get('joins', []) if j.get('ko')]
    if joins:
        return ' · '.join(dict.fromkeys(joins)), en
    if en and en.lower() in ko_country:
        return ko_country[en.lower()], en
    return en, en


def enrich_don(item, raw, ko_country):
    summ = strip(raw.get('Summary') or raw.get('Overview') or '')
    assess = strip(raw.get('Assessment') or '')
    advice = strip(raw.get('Advice') or '')
    facts = {}
    m = re.search(r'(\d[\d,\s]*)\s+(?:laboratory[- ]confirmed|confirmed)\s+cases', summ)
    if m:
        facts['cases'] = num(m.group(1))
    m = re.search(r'including\s+(\d[\d,\s]*)\s+(?:confirmed\s+)?deaths', summ) or re.search(r'(\d[\d,\s]*)\s+deaths', summ)
    if m:
        facts['deaths'] = num(m.group(1))
    m = re.search(r'(?:CFR|case fatality (?:ratio|rate))[^0-9%]{0,25}([\d.]+)\s*%', summ)
    if m:
        facts['cfr'] = m.group(1) + '%'
    m = re.search(r'(\d[\d,\s]*)\s+suspected', summ)
    if m:
        facts['suspected'] = num(m.group(1))
    asof = parse_asof(summ)
    if asof:
        facts['as_of'] = asof
    # 위험 평가 — 문장마다 수준과 범위를 읽는다
    risk = []
    for sent in re.split(r'(?<=[.;])\s+', assess):
        if not re.search(r'\brisk', sent, re.I):
            continue
        # "…in the DRC was assessed as very high, the risk for countries sharing land borders … high,
        #  and the risks for the rest of the region and at the global level … low" — 절마다 하나씩
        for cl in re.split(r',\s*(?:and\s+|while\s+)?|;\s*|\s+and\s+the\s+risk', sent):
            lv = re.search(r'\b(very high|high|moderate|low)\b', cl, re.I)
            if not lv:
                continue
            c = cl.lower()
            scope = ('세계' if 'global' in c else '지역' if 'region' in c else
                     '인접국' if ('border' in c or 'neighbour' in c or 'neighbor' in c) else '국가')
            risk.append([scope, RISK.get(lv.group(1).lower(), lv.group(1))])
    if risk:
        dedup = {}
        for sc, lv in risk:
            dedup.setdefault(sc, lv)
        facts['risk'] = [[k, v] for k, v in dedup.items()]
    if re.search(r'advises against any restriction', advice, re.I):
        facts['travel'] = '여행·교역 제한 권고 안 함'
    elif re.search(r'restriction', advice, re.I):
        facts['travel'] = '여행·교역 관련 권고 있음(원문 확인)'

    dz_ko, dz_en = _dz_ko_en(item)
    c_ko, c_en = _country_ko(item, ko_country)
    bits = []
    head = f'{dz_ko}({dz_en})' if dz_ko else dz_en
    if c_ko:
        head += f' — {c_ko}' + (f'({c_en})' if c_en and c_ko != c_en else '')
    bits.append(head + '.')
    if 'cases' in facts:
        s = (f"{facts['as_of']} 기준 " if facts.get('as_of') else '') + f"확진 {facts['cases']:,}명"
        if 'deaths' in facts:
            s += f", 사망 {facts['deaths']:,}명"
        if 'cfr' in facts:
            s += f"(치명률 CFR {facts['cfr']})"
        if 'suspected' in facts:
            s += f", 의심 {facts['suspected']:,}명"
        bits.append(s + '.')
    if facts.get('risk'):
        bits.append('WHO 위험 평가: ' + ' · '.join(f'{sc} {lv}' for sc, lv in facts['risk']) + '.')
    if facts.get('travel'):
        bits.append(facts['travel'] + '.')
    item['ko'] = ' '.join(bits)
    item['facts'] = facts
    item['en'] = sentences(summ, 3)
    body = (raw.get('Overview') or '') + (raw.get('Epidemiology') or '') + (raw.get('Response') or '')
    item['figs'] = figures(body)
    item['tables'] = tables(body)


def enrich_cdc_travel(item, page, ko_country):
    lvl = item.get('level')
    facts = {}
    if lvl in LEVEL:
        facts['level'] = lvl
        facts['level_en'], facts['level_ko'] = LEVEL[lvl]
    points, figs = [], []
    if page:
        m = re.search(r'<h[23][^>]*>\s*Key points\s*</h[23]>\s*<ul>([\s\S]*?)</ul>', page, re.I)
        if m:
            points = [strip(li)[:260] for li in re.findall(r'<li[^>]*>([\s\S]*?)</li>', m.group(1))][:5]
        og = re.search(r'property="og:image" content="([^"]+)"', page)
        for im in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', page):
            src = im.group(1)
            if re.search(r'map', src, re.I) and src.startswith('http'):
                figs.append({'src': src, 'caption': '발생 지역 지도(CDC)'})
                break
        if not figs and og and re.search(r'map', og.group(1), re.I):
            figs.append({'src': og.group(1), 'caption': '발생 지역 지도(CDC)'})
    title = re.sub(r'^Level\s*\d\s*-\s*', '', item.get('title') or '')
    dz_ko, dz_en = _dz_ko_en({**item, 'title': title})
    m = re.search(r'\bin\s+(.+)$', dz_en)
    country_en = m.group(1).strip() if m else ''
    dz_en = re.sub(r'\s+in\s+.+$', '', dz_en)
    joins = [j['ko'] for j in item.get('joins', []) if j.get('ko')]
    c_ko = ' · '.join(dict.fromkeys(joins)) if joins else ko_country.get(country_en.lower(), country_en)
    bits = []
    if lvl in LEVEL:
        bits.append(f'CDC 여행 건강 알림 {lvl}단계 — {LEVEL[lvl][1]}({LEVEL[lvl][0]}).')
    bits.append((f'{dz_ko}({dz_en})' if dz_ko else dz_en) + (f' — {c_ko}' + (f'({country_en})' if country_en and c_ko != country_en else '') if c_ko else '') + '.')
    if points:
        bits.append('핵심 사항(Key points)은 아래 원문에 용어를 달아 두었다.')
    item['ko'] = ' '.join(bits)
    item['facts'] = facts
    item['en'] = ' '.join(points) if points else (item.get('summary') or '')
    item['en_list'] = points
    item['figs'] = figs
    item['tables'] = []


def enrich_cdc_outbreak(item, ko_country):
    d = item.get('summary') or ''
    facts = {}
    for key, pat in (('cases', r'(\d[\d,]*)\s+(?:people|illnesses|cases|infections)'),
                     ('hospitalized', r'(\d[\d,]*)\s+hospitalizations?'),
                     ('deaths', r'(\d[\d,]*)\s+deaths?'),
                     ('states', r'(\d[\d,]*)\s+states')):
        m = re.search(pat, d, re.I)
        if m:
            facts[key] = num(m.group(1))
    dz_ko, dz_en = _dz_ko_en(item)
    bits = ['미국 CDC 발생 조사 — ' + (f'{dz_ko}({dz_en})' if dz_ko else item['title']) + '.']
    s = []
    if 'cases' in facts:
        s.append(f"환자 {facts['cases']:,}명")
    if 'hospitalized' in facts:
        s.append(f"입원 {facts['hospitalized']:,}명")
    if 'deaths' in facts:
        s.append(f"사망 {facts['deaths']:,}명")
    if 'states' in facts:
        s.append(f"{facts['states']}개 주")
    if s:
        bits.append(' · '.join(s) + '.')
    item['ko'] = ' '.join(bits)
    item['facts'] = facts
    item['en'] = sentences(d, 3)
    item['figs'] = []
    item['tables'] = []


def enrich_kdca(item, page):
    facts, bits = {}, []
    if page:
        t = strip(re.sub(r'<(script|style)[\s\S]*?</\1>', '', page))
        m = re.search(r'담당부서\s*([^\s]+(?:\s[^\s]+)?)\s+연락처', t)
        if m:
            facts['dept'] = m.group(1).strip()
        m = re.search(r'작성일\s*(\d{4}\.\d{2}\.\d{2})', t)
        if m:
            facts['written'] = m.group(1).replace('.', '-')
        body = re.search(r'연락처\s*[\d\-]+\s*(.*?)(?:다운받기|미리보기|본 공공저작물)', t)
        if body:
            sent = body.group(1).strip()
            sent = re.split(r'\s*(?:첨부|붙임|※|끝\.)', sent)[0]              # 첨부 목록부터는 사실 칸으로
            sent = re.sub(r'\S+\.(?:pdf|hwp|hwpx|xlsx|docx|zip)', '', sent, flags=re.I).strip()
            # '1. 관련근거 가.' 같은 번호 머리, 닫는 따옴표만 남은 조각은 문장이 아니다
            parts = [x.strip(' \'"’”」』') for x in re.split(r'(?<=[.다])\s+', sent)]
            parts = [x for x in parts if len(x) >= 10 and not re.match(r'^\d+\.\s', x)]
            sent = ' '.join(parts[:2]).strip()                              # 두 문장까지
            if sent:
                bits.append(sent[:220])
        # 첨부 파일명은 <li> 본문에 통째로 있다(공백 포함). 공백으로 자르면 '2026.8)_전자용.pdf'처럼 앞이 잘린다
        files = re.findall(r'<li>\s*(?:<!--.*?-->\s*)?([^<]{4,120}?\.(?:pdf|hwp|hwpx|xlsx|docx|zip))\s*<div>', page, re.I | re.S)
        files = [' '.join(f.split()) for f in files]
        if not files:
            files = re.findall(r'([^\s]+\.(?:pdf|hwp|hwpx|xlsx|docx|zip))', t, re.I)
        files = list(dict.fromkeys(f for f in files if len(f) > 6))
        if files:
            facts['files'] = files[:4]
    tail = []
    if facts.get('dept'):
        tail.append(f"담당 {facts['dept']}")
    if facts.get('files'):
        tail.append(f"첨부 {len(facts['files'])}건: " + ' · '.join(facts['files'][:3]))
    if tail:
        bits.append(' · '.join(tail) + '.')
    item['ko'] = ' '.join(bits) if bits else ''
    item['facts'] = facts
    item['en'] = ''
    item['figs'] = []
    item['tables'] = []


def enrich(item, raw_pages, ko_country):
    """raw_pages: {'don': WHO API 원본 dict, 'page': 받아 둔 HTML 문자열}"""
    src = item.get('source')
    try:
        if src == 'WHO DON':
            enrich_don(item, raw_pages.get('don') or {}, ko_country)
        elif src == 'CDC 여행알림':
            enrich_cdc_travel(item, raw_pages.get('page') or '', ko_country)
        elif src == 'CDC 발생조사':
            enrich_cdc_outbreak(item, ko_country)
        elif src == 'KDCA 지침':
            enrich_kdca(item, raw_pages.get('page') or '')
    except Exception as e:  # noqa: BLE001 — 한 항목이 깨져도 판은 나가야 한다
        item.setdefault('ko', '')
        item['enrich_err'] = str(e)[:120]
    item['terms'] = find_terms(item.get('en', ''))
    item['enrich_v'] = ENRICH_V
    return item
