#!/usr/bin/env python3
"""📡 감염병 상황판 — 매일 아침 공개 출처를 긁어 '오늘 새로 올라온 것'을 만든다.

GitHub Actions(.github/workflows/daily.yml)가 매일 06:00 KST에 실행한다. 손으로도 돌릴 수 있다.

출처 (모두 공개, 키 없음)
 - WHO 질병 발생 뉴스(DON)      who.int OData API
 - CDC 여행 건강 알림            wwwnc.cdc.gov RSS
 - CDC 발생조사 알림             tools.cdc.gov RSS — 병원체가 분명한 발생 조사
 - KDCA 지침·매뉴얼 게시판        kdca.go.kr/bbs/kdca/55 — 새 지침이 오르면 ② 갱신 신호

이 페이지가 남과 다른 점은 수집이 아니라 결합이다. 항목마다 질병명·나라를 알아내어
 - 질병 → 도감·현장카드·병원체 형태
 - 나라 → 유입지도 (검역관리지역 지정 여부 · 직항 도착 여객)
를 한 줄로 붙인다. "WHO가 오늘 보고한 그 나라, 우리는 지정돼 있나, 직항은 있나."

출처가 죽어도 페이지는 죽지 않는다. 출처별로 성공/실패와 마지막 성공 시각을 적고,
'가장 최근 발행이 며칠 전인지'도 함께 적는다 — 조용한 출처를 고장으로 오해하지 않도록.
(WHO 질병 발생 뉴스는 한 달에 두세 건이라 열흘 넘게 조용한 것이 정상이다.)
"""
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from portal_tools import inject, inject_nav  # noqa: E402

OUT_DIR = os.path.join(ROOT, 'portal', 'daily')
DATA_DIR = os.path.join(OUT_DIR, 'data')
ITEMS = os.path.join(DATA_DIR, 'items.json')
STATUS = os.path.join(DATA_DIR, 'status.json')
KST = timezone(timedelta(hours=9))
UA = 'Mozilla/5.0 (compatible; disease-archive-daily/1.0; +https://soonryu74.github.io/disease/)'
SITE = 'https://soonryu74.github.io/disease/'
KEEP = 400            # 항목 저장 상한
SUBSCRIBE_FORM_URL = os.environ.get('SUBSCRIBE_FORM_URL', '')  # 이메일 신청 폼(외부 서비스) 주소

# 영어 낱말 → 도감 질병명. 제목·요약에서 찾는다. 긴 것부터 맞춘다.
DISEASE_KW = [
    ('marburg', '마버그열'), ('ebola', '에볼라바이러스병'), ('bundibugyo', '에볼라바이러스병'),
    ('lassa', '라싸열'), ('crimean-congo', '크리미안콩고출혈열'), ('cchf', '크리미안콩고출혈열'),
    ('rift valley', '리프트밸리열'), ('nipah', '니파바이러스감염증'), ('mers', '중동호흡기증후군'),
    ('middle east respiratory', '중동호흡기증후군'), ('plague', '페스트'), ('anthrax', '탄저'),
    ('diphtheria', '디프테리아'), ('smallpox', '두창'), ('mpox', '엠폭스'), ('monkeypox', '엠폭스'),
    ('avian influenza', '동물인플루엔자 인체감염증'), ('h5n1', '동물인플루엔자 인체감염증'),
    ('h7n9', '동물인플루엔자 인체감염증'), ('h5n', '동물인플루엔자 인체감염증'), ('h9n2', '동물인플루엔자 인체감염증'),
    ('influenza a(h', '동물인플루엔자 인체감염증'), ('cholera', '콜레라'), ('measles', '홍역'),
    ('polio', '폴리오'), ('yellow fever', '황열'), ('dengue', '뎅기열'), ('chikungunya', '치쿤구니야열'),
    ('zika', '지카바이러스감염증'), ('malaria', '말라리아'), ('meningococcal', '수막구균 감염증'),
    ('meningitis', '수막구균 감염증'), ('pertussis', '백일해'), ('whooping cough', '백일해'),
    ('hepatitis a', 'A형간염'), ('hepatitis e', 'E형간염'), ('typhoid', '장티푸스'),
    ('paratyphoid', '파라티푸스'), ('rabies', '공수병'), ('west nile', '웨스트나일열'),
    ('japanese encephalitis', '일본뇌염'), ('leptospirosis', '렙토스피라증'), ('tuberculosis', '결핵'),
    ('covid', '코로나바이러스감염증-19'), ('sars-cov-2', '코로나바이러스감염증-19'),
    ('hantavirus', '신증후군출혈열'), ('sfts', '중증열성혈소판감소증후군'), ('tick-borne encephalitis', '진드기매개뇌염'),
    ('brucell', '브루셀라증'), ('legionell', '레지오넬라증'), ('shigell', '세균성이질'),
    ('e. coli', '장출혈성대장균감염증'), ('stec', '장출혈성대장균감염증'), ('botulism', '보툴리눔독소증'),
    ('tularemia', '야토병'), ('varicella', '수두'), ('chickenpox', '수두'), ('mumps', '유행성이하선염'),
    ('rubella', '풍진'), ('scarlet fever', '성홍열'), ('hib', 'b형헤모필루스인플루엔자'),
    ('pneumococc', '폐렴구균 감염증'), ('candida auris', '칸디다오리스감염증'), ('syphilis', '매독'),
    ('gonorrh', '임질'), ('influenza', '인플루엔자'), ('scrub typhus', '쯔쯔가무시증'),
    ('leprosy', '한센병'), ('hansen', '한센병'), ('tetanus', '파상풍'), ('melioidosis', '유비저'),
    ('q fever', '큐열'), ('lyme', '라임병'), ('vibrio vulnificus', '비브리오패혈증'),
    ('creutzfeldt', '크로이츠펠트-야콥병(CJD)·변종CJD'), ('hiv', '후천성면역결핍증'),
    ('hepatitis b', 'B형간염'), ('hepatitis c', 'C형간염'), ('enterovirus', '엔테로바이러스감염증'),
    ('hand, foot', '수족구병'), ('hpv', '사람유두종바이러스(HPV) 감염증'),
]
# 한글 낱말 (KDCA 게시판 제목용) — 도감 이름 자체가 제목에 들어가면 그대로 잡힌다.
# 영어 나라 이름 별칭 → Natural Earth 이름. 지도 파일의 name/name_long/admin 으로 못 잡는 것만.
COUNTRY_ALIAS = {
    'democratic republic of the congo': 'COD', 'drc': 'COD', 'dr congo': 'COD', 'congo, democratic republic': 'COD',
    'republic of the congo': 'COG', 'united republic of tanzania': 'TZA', 'viet nam': 'VNM',
    'türkiye': 'TUR', 'turkiye': 'TUR', 'turkey': 'TUR', 'republic of korea': 'KOR', 'south korea': 'KOR',
    "democratic people's republic of korea": 'PRK', 'dprk': 'PRK', 'russian federation': 'RUS',
    'iran (islamic republic of)': 'IRN', 'islamic republic of iran': 'IRN', "lao people's democratic republic": 'LAO',
    'syrian arab republic': 'SYR', 'bolivia (plurinational state of)': 'BOL', 'venezuela (bolivarian republic of)': 'VEN',
    'united states of america': 'USA', 'united states': 'USA', 'usa': 'USA', 'united kingdom': 'GBR', 'uk': 'GBR',
    'czechia': 'CZE', 'czech republic': 'CZE', "côte d'ivoire": 'CIV', "cote d'ivoire": 'CIV', 'ivory coast': 'CIV',
    'eswatini': 'SWZ', 'swaziland': 'SWZ', 'myanmar': 'MMR', 'burma': 'MMR', 'timor-leste': 'TLS', 'east timor': 'TLS',
    'north macedonia': 'MKD', 'republic of moldova': 'MDA', 'the gambia': 'GMB', 'gambia': 'GMB',
    'hong kong': 'HKG', 'macao': 'MAC', 'macau': 'MAC', 'singapore': 'SGP', 'maldives': 'MDV', 'bahrain': 'BHR',
    'mauritius': 'MUS', 'seychelles': 'SYC', 'cabo verde': 'CPV', 'cape verde': 'CPV', 'comoros': 'COM',
    'sao tome and principe': 'STP', 'guam': 'GUM', 'saudi arabia': 'SAU', 'kingdom of saudi arabia': 'SAU',
    'united arab emirates': 'ARE', 'uae': 'ARE', 'taiwan': 'TWN', 'china': 'CHN', "people's republic of china": 'CHN',
    'philippines': 'PHL', 'the philippines': 'PHL', 'netherlands': 'NLD', 'the netherlands': 'NLD',
    'bahamas': 'BHS', 'the bahamas': 'BHS', 'south sudan': 'SSD', 'sudan': 'SDN', 'niger': 'NER', 'nigeria': 'NGA',
    'guinea': 'GIN', 'guinea-bissau': 'GNB', 'equatorial guinea': 'GNQ', 'papua new guinea': 'PNG',
    'dominican republic': 'DOM', 'dominica': 'DMA', 'central african republic': 'CAF', 'south africa': 'ZAF',
    'somalia': 'SOM', 'somaliland': 'SOM', 'western sahara': 'ESH', 'palestine': 'PSE', 'occupied palestinian territory': 'PSE',
    'kosovo': 'XKX', 'micronesia': 'FSM', 'marshall islands': 'MHL', 'solomon islands': 'SLB', 'vanuatu': 'VUT',
    'samoa': 'WSM', 'tonga': 'TON', 'fiji': 'FJI', 'kiribati': 'KIR', 'tuvalu': 'TUV', 'nauru': 'NRU', 'palau': 'PLW',
    'cook islands': 'COK', 'new caledonia': 'NCL', 'french polynesia': 'PYF', 'réunion': 'REU', 'reunion': 'REU',
    'mayotte': 'MYT', 'french guiana': 'GUF', 'guadeloupe': 'GLP', 'martinique': 'MTQ', 'puerto rico': 'PRI',
    'nicaragua': 'NIC', 'yemen': 'YEM', 'indonesia': 'IDN',
}
NON_COUNTRY = ['sub-saharan africa', 'multi-country', 'multi-locations', 'multiple countries', 'global', 'region of',
               'the americas', 'africa', 'europe', 'asia', 'western pacific', 'eastern mediterranean', 'south-east asia']


def now_kst():
    return datetime.now(KST)


def curl(url, tries=5, timeout=60):
    """망이 자주 끊긴다. 지수 백오프로 다시 건다. 실패하면 None."""
    import time
    for i in range(1, tries + 1):
        p = subprocess.run(['curl', '-sS', '-L', '-m', str(timeout), '-A', UA, url], capture_output=True)
        if p.returncode == 0 and p.stdout and len(p.stdout) > 200:
            return p.stdout
        time.sleep(i * 2)
    return None


def strip(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or ''))).strip()


# ── 출처 ─────────────────────────────────────────────────────────────
def src_who_don():
    raw = curl('https://www.who.int/api/news/diseaseoutbreaknews?$orderby=PublicationDateAndTime%20desc&$top=30')
    if not raw:
        raise RuntimeError('접속 실패')
    out = []
    for v in json.loads(raw)['value']:
        out.append({'id': 'who:' + v['UrlName'], 'source': 'WHO DON', 'title': strip(v.get('Title')),
                    'link': 'https://www.who.int/emergencies/disease-outbreak-news/item/' + v['UrlName'],
                    'date': (v.get('PublicationDate') or '')[:10],
                    'summary': strip(v.get('Summary') or v.get('Overview') or '')[:320]})
    return out


def parse_rss(raw):
    s = raw.decode('utf-8', 'replace')
    items = []
    for it in re.findall(r'<item>(.*?)</item>', s, re.S):
        t = re.search(r'<title>(.*?)</title>', it, re.S)
        l = re.search(r'<link>(.*?)</link>', it, re.S)
        d = re.search(r'<pubDate>(.*?)</pubDate>', it, re.S)
        desc = re.search(r'<description>(.*?)</description>', it, re.S)
        date = ''
        if d:
            for fmt in ('%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z'):
                try:
                    date = datetime.strptime(d.group(1).strip(), fmt).strftime('%Y-%m-%d')
                    break
                except ValueError:
                    pass
        items.append({'title': strip(t.group(1)) if t else '', 'link': strip(l.group(1)) if l else '',
                      'date': date, 'summary': strip(re.sub(r'^<!\[CDATA\[|\]\]>$', '', desc.group(1)))[:320] if desc else ''})
    return items


def src_cdc_travel():
    raw = curl('https://wwwnc.cdc.gov/travel/rss/notices.xml')
    if not raw:
        raise RuntimeError('접속 실패')
    out = []
    for it in parse_rss(raw):
        m = re.match(r'Level\s*(\d)\s*-\s*(.*)', it['title'])
        out.append({'id': 'cdc:' + it['link'].rstrip('/').split('/')[-1], 'source': 'CDC 여행알림',
                    'title': it['title'], 'link': it['link'], 'date': it['date'], 'summary': it['summary'],
                    'level': int(m.group(1)) if m else None})
    return out


def src_cdc_outbreaks():
    """CDC 발생 조사 알림. WHO 일반 뉴스를 대신한다 —
    그 피드는 기관 소식(사무총장 방문 등)이 대부분이라 25건 중 감염병은 2건뿐이었다."""
    raw = curl('https://tools.cdc.gov/api/v2/resources/media/285676.rss')
    if not raw:
        raise RuntimeError('접속 실패')
    out = []
    for it in parse_rss(raw):
        if not it['title']:
            continue
        out.append({'id': 'cdcout:' + it['link'].rstrip('/').split('/')[-1], 'source': 'CDC 발생조사',
                    'title': it['title'], 'link': it['link'], 'date': it['date'], 'summary': it['summary']})
    return out


def src_kdca_guides():
    raw = curl('https://www.kdca.go.kr/bbs/kdca/55/artclList.do')
    if not raw:
        raise RuntimeError('접속 실패')
    s = raw.decode('utf-8', 'replace')
    rows = re.findall(r"jf_viewArtcl\('kdca',\s*'55',\s*'(\d+)'\)[^>]*>(.*?)</a>", s, re.S)
    dates = re.findall(r'\d{4}\.\d{2}\.\d{2}', s)
    if not rows:
        raise RuntimeError('목록 형식이 바뀜')
    out = []
    for i, (aid, t) in enumerate(rows):
        out.append({'id': 'kdca55:' + aid, 'source': 'KDCA 지침', 'title': strip(t),
                    'link': f'https://www.kdca.go.kr/bbs/kdca/55/{aid}/artclView.do',
                    'date': dates[i].replace('.', '-') if i < len(dates) else '', 'summary': ''})
    return out


# (id, 이름, 수집함수, 대략적 발행 간격(일) — 이보다 훨씬 오래 조용하면 '확인 필요'로 표시)
SRC_PREFIX = {'who_don': 'who:', 'cdc_travel': 'cdc:', 'cdc_outbreak': 'cdcout:', 'kdca_guides': 'kdca55:'}
SOURCES = [
    ('who_don', 'WHO 질병 발생 뉴스', src_who_don, 20),
    ('cdc_travel', 'CDC 여행 건강 알림', src_cdc_travel, 20),
    ('cdc_outbreak', 'CDC 발생조사', src_cdc_outbreaks, 45),
    ('kdca_guides', 'KDCA 지침·매뉴얼 게시판', src_kdca_guides, 30),
]


# ── 결합 ─────────────────────────────────────────────────────────────
def load_join():
    geo = json.load(open(os.path.join(ROOT, '15_해외유입_지도', 'data', '세계지도.json'), encoding='utf-8'))
    names = {}
    for c in geo['countries'] + geo['points']:
        for k in ('name', 'name_long', 'admin'):
            if c.get(k):
                names[c[k].lower()] = c['iso']
    for k, v in COUNTRY_ALIAS.items():
        names[k] = v
    # 긴 이름부터 맞춰야 'guinea'가 'papua new guinea'를 가로채지 않는다
    name_list = sorted(names.items(), key=lambda kv: -len(kv[0]))
    inflow = json.load(open(os.path.join(ROOT, '15_해외유입_지도', 'data', '유입_종합.json'), encoding='utf-8'))
    rows = {r['iso']: r for r in inflow['rows']}
    quar = set(inflow['quar_diseases'])
    dogam = {}
    for c in geo['countries'] + geo['points']:
        dogam[c['iso']] = c['ko']
    return name_list, rows, quar, dogam


def norm_dz(s):
    return re.sub(r'[\s()·・\-]', '', s or '')


def tag(item, name_list, rows, quar, ko_name):
    text = (item['title'] + ' ' + item.get('summary', '')).lower()
    title = item['title'].lower()
    diseases = []
    for k, d in DISEASE_KW:  # 낱말 경계 — 'typhoid'가 'paratyphoid' 안에서 잡히지 않게
        if re.search(r'(?<![a-z])' + re.escape(k), text) and d not in diseases:
            diseases.append(d)
    # 한글 제목(KDCA)은 도감 이름으로
    for d in KO_NAMES:
        if d in item['title'] and d not in diseases:
            diseases.append(d)

    def find_countries(s, min_len, cap):
        # 긴 이름을 먼저 맞추고 그 자리를 지운다 — 'Republic of the Congo'가
        # 'Democratic Republic of the Congo' 안에서 다시 잡히지 않게
        found = []
        for name, iso in name_list:
            if len(name) < min_len:
                continue
            m = re.search(r'(?<![a-z])' + re.escape(name) + r'(?![a-z])', s)
            if m:
                s = s[:m.start()] + ' ' * (m.end() - m.start()) + s[m.end():]
                if iso not in found:
                    found.append(iso)
                if len(found) >= cap:
                    break
        return found
    countries = find_countries(title, 4, 4)
    if not countries:  # 요약에서 한 번 더 (제목에 나라가 없을 때만)
        countries = find_countries(text, 5, 3)
    item['diseases'] = diseases[:4]
    item['countries'] = countries[:4]
    item['multi'] = any(k in title for k in NON_COUNTRY)
    # 결합: (질병, 나라)마다 우리 검역 지정·직항 여객
    joins = []
    for iso in item['countries']:
        r = rows.get(iso)
        if not r:
            continue
        desig = {norm_dz(x) for x in r['q_general'] + r['q_priority']}
        for d in item['diseases']:
            if d not in quar and norm_dz(d) not in {norm_dz(q) for q in quar}:
                continue
            joins.append({'iso': iso, 'ko': r['ko'], 'disease': d,
                          'designated': norm_dz(d) in desig, 'priority': d in r['q_priority'],
                          'air': r['air_direct'], 'nat': r['nat_entries']})
        if not joins or all(j['iso'] != iso for j in joins):
            joins.append({'iso': iso, 'ko': r['ko'], 'disease': None, 'designated': None, 'priority': False,
                          'any': len(set(r['q_general'] + r['q_priority'])), 'air': r['air_direct'], 'nat': r['nat_entries']})
    item['joins'] = joins
    return item


KO_NAMES = []


def load_ko_names():
    global KO_NAMES
    try:
        d = json.load(open(os.path.join(ROOT, '05_감염병_질병정보', '병원체_형태분류.json'), encoding='utf-8'))
        KO_NAMES = sorted((x['name'] for x in d['diseases']), key=len, reverse=True)
    except Exception:
        KO_NAMES = []


# ── 저장·렌더 ─────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = now_kst().strftime('%Y-%m-%d')
    run_at = now_kst().strftime('%Y-%m-%d %H:%M KST')
    old = json.load(open(ITEMS, encoding='utf-8')) if os.path.exists(ITEMS) else []
    status = json.load(open(STATUS, encoding='utf-8')) if os.path.exists(STATUS) else {}
    by_id = {x['id']: x for x in old}
    load_ko_names()
    name_list, rows, quar, ko = load_join()

    fetched, by_source = [], {}
    for sid, label, fn, cadence in SOURCES:
        st = status.get(sid, {})
        try:
            items = fn()
            st.update({'label': label, 'ok': True, 'last_ok': run_at, 'count': len(items), 'error': '',
                       'cadence': cadence})
            fetched += items
            by_source[sid] = items
            print(f'  ✓ {label}: {len(items)}건')
        except Exception as e:  # noqa: BLE001
            st.update({'label': label, 'ok': False, 'error': str(e)[:120], 'last_try': run_at,
                       'cadence': cadence})
            st.setdefault('last_ok', '')
            print(f'  ✗ {label}: {e}')
        status[sid] = st
    new_count = 0
    for it in fetched:
        if it['id'] in by_id:
            by_id[it['id']].update({k: v for k, v in it.items() if k in ('title', 'summary', 'date', 'level')})
        else:
            it['first_seen'] = today
            by_id[it['id']] = it
            new_count += 1
    items = list(by_id.values())
    for it in items:
        tag(it, name_list, rows, quar, ko)
    # 발행일 내림차순이 먼저다. 화면도 발행일로 묶으므로 순서가 어긋나면 안 된다.
    items.sort(key=lambda x: (x.get('date') or '', x.get('first_seen', '')), reverse=True)
    items = items[:KEEP]
    # 출처마다 '가장 최근 발행일'과 그 뒤로 며칠이 지났는지 — 조용한 것과 고장난 것을 가른다.
    # 수집이 성공해도 발행이 오래 없으면 화면에 그렇게 적어야 사용자가 의심하지 않는다.
    td = datetime.strptime(today, '%Y-%m-%d').date()
    for sid, label, _fn, cadence in SOURCES:
        pref = SRC_PREFIX[sid]
        ds = sorted({x['date'] for x in items if x['id'].startswith(pref) and x.get('date')}, reverse=True)
        st = status[sid]
        if ds:
            age = (td - datetime.strptime(ds[0], '%Y-%m-%d').date()).days
            st['latest'] = ds[0]
            st['age_days'] = age
            st['quiet'] = age > cadence * 2   # 평소 간격의 두 배를 넘게 조용하면 확인 필요
        else:
            st['latest'] = ''
            st['age_days'] = None
            st['quiet'] = True
    # 더 이상 쓰지 않는 출처는 원장에서 지운다. 남겨 두면 화면에 죽은 딱지가 붙는다.
    for k in [k for k in status if k != '_run' and k not in SRC_PREFIX]:
        del status[k]
    status['_run'] = {'run_at': run_at, 'today': today, 'new': new_count, 'total': len(items)}
    json.dump(status, open(STATUS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(DATA_DIR, 'new_count.txt'), 'w').write(str(new_count))
    print(f'  오늘 새 항목 {new_count} · 보관 {len(items)}')

    render(items, status, today, run_at)
    write_feed(items)
    write_mail(items, today, run_at)


def render(items, status, today, run_at):
    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'daily.template.html'), encoding='utf-8').read()
    # 첫 수집인가 — 보관분이 전부 오늘 처음 잡혔으면 '새 항목'이라는 말이 뜻을 잃는다.
    first_run = bool(items) and all(x.get('first_seen') == today for x in items)
    data = {'items': items, 'status': status, 'today': today, 'run_at': run_at, 'site': SITE,
            'first_run': first_run, 'subscribe_form': SUBSCRIBE_FORM_URL}
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = os.path.join(OUT_DIR, 'index.html')
    open(out, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    inject(out, 1)
    inject_nav(out, 1, 'daily')
    print(f'→ portal/daily/index.html  {os.path.getsize(out):,}B')


def write_feed(items):
    def esc(s):
        return html.escape(s or '', quote=False)
    parts = []
    for it in items[:60]:
        tags = ' · '.join(it.get('diseases', []) + [j['ko'] for j in it.get('joins', []) if j.get('ko')][:3])
        joins = '; '.join(f"{j['ko']} {'중점' if j['priority'] else ('검역관리지역' if j['designated'] else '미지정')}"
                          + (f"({j['disease']})" if j.get('disease') else '') for j in it.get('joins', []))
        desc = esc(it.get('summary', '')) + (f' — 태그: {esc(tags)}' if tags else '') + (f' — 우리 검역: {esc(joins)}' if joins else '')
        try:
            pub = datetime.strptime(it.get('date') or it['first_seen'], '%Y-%m-%d').replace(tzinfo=KST).strftime('%a, %d %b %Y 06:00:00 +0900')
        except ValueError:
            pub = ''
        parts.append(f"<item><title>[{esc(it['source'])}] {esc(it['title'])}</title><link>{esc(it['link'])}</link>"
                     f"<guid isPermaLink=\"false\">{esc(it['id'])}</guid><pubDate>{pub}</pubDate>"
                     f"<description>{desc}</description></item>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
           '<title>감염병 상황판 — 감염병 자료 아카이브</title>'
           f'<link>{SITE}daily/</link>'
           '<description>WHO 질병 발생 뉴스 · CDC 여행 건강 알림 · KDCA 지침 게시판을 매일 아침 모아 우리 검역 지정·직항 여객과 붙인다.</description>'
           '<language>ko</language>' + ''.join(parts) + '</channel></rss>')
    open(os.path.join(OUT_DIR, 'feed.xml'), 'w', encoding='utf-8').write(xml)


def write_mail(items, today, run_at):
    """오늘 새로 올라온 것만 담은 짧은 편지. daily.yml이 SMTP 비밀이 있을 때만 보낸다."""
    new = [x for x in items if x.get('first_seen') == today]
    def esc(s):
        return html.escape(s or '', quote=False)
    rows = []
    for it in new:
        joins = ' · '.join(f"{j['ko']} {'중점' if j['priority'] else ('지정' if j['designated'] else '미지정')}"
                           + (f"({j['disease']})" if j.get('disease') else '') for j in it.get('joins', []))
        rows.append(f'<li style="margin:0 0 10px"><b>[{esc(it["source"])}]</b> <a href="{esc(it["link"])}">{esc(it["title"])}</a>'
                    + (f'<br><span style="color:#555;font-size:13px">{esc(it.get("summary","")[:200])}</span>' if it.get('summary') else '')
                    + (f'<br><span style="color:#0A4A43;font-size:13px">우리 검역: {esc(joins)}</span>' if joins else '') + '</li>')
    body = (f'<div style="font-family:sans-serif;max-width:640px"><h2 style="margin:0 0 4px">감염병 상황판 {today}</h2>'
            f'<p style="color:#555;margin:0 0 14px">새로 올라온 것 {len(new)}건 · {run_at}</p>'
            + (f'<ul style="padding-left:18px">{"".join(rows)}</ul>' if rows else '<p>오늘은 새로 올라온 것이 없다.</p>')
            + f'<p style="font-size:12px;color:#777">전체 보기: <a href="{SITE}daily/">{SITE}daily/</a> · RSS: {SITE}daily/feed.xml'
            f'<br>감염병 자료 아카이브 · 지음웍스 jieumworks.com</p></div>')
    open(os.path.join(DATA_DIR, 'mail.html'), 'w', encoding='utf-8').write(body)
    open(os.path.join(DATA_DIR, 'mail_subject.txt'), 'w', encoding='utf-8').write(f'[감염병 상황판] {today} 새 항목 {len(new)}건')


if __name__ == '__main__':
    print('상황판 수집', now_kst().strftime('%Y-%m-%d %H:%M KST'))
    main()
