#!/usr/bin/env python3
"""⑤ 질병정보 도감 → portal/dogam/ 정적 페이지 생성.

05_감염병_질병정보/제1~4급_질병정보.md 의 `### 질병명` + `- **필드**: 값` 구조를
파싱하고, 별칭사전.json의 옛 이름·별칭을 검색 색인에 합쳐 검색 가능한
단일 페이지 도감을 만든다. 허브(portal/index.html)와 같은 색·타이포 토큰 사용.
"""
import html as H
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '05_감염병_질병정보')
OUT = os.path.join(ROOT, 'portal', 'dogam', 'index.html')

GRADES = [
    ('1', '제1급', '제1급_질병정보.md', '발생 즉시 신고 · 음압격리 등 높은 수준의 격리'),
    ('2', '제2급', '제2급_질병정보.md', '24시간 이내 신고 · 격리 필요'),
    ('3', '제3급', '제3급_질병정보.md', '24시간 이내 신고 · 발생 추이 감시'),
    ('4', '제4급', '제4급_질병정보.md', '표본감시 · 7일 이내 신고'),
]

SKIP_HEAD = re.compile(r'출처|^\(참고\)|⚠️|원문 오기')

# 제4급 §C 항생제내성균 4종 — 원문이 표 형태라 표에서 뽑아 정식 명칭으로 수록
RESIST_NAMES = {
    'VRE': '반코마이신내성장알균(VRE) 감염증',
    'MRSA': '메티실린내성황색포도알균(MRSA) 감염증',
    'MRPA': '다제내성녹농균(MRPA) 감염증',
    'MRAB': '다제내성아시네토박터바우마니균(MRAB) 감염증',
}


def md_inline(s: str) -> str:
    s = H.escape(s.strip())
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', s)
    # 저장소 내부 상대링크는 웹에서 깨지므로 텍스트만 남기고, http 링크는 살린다
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)
    return s


def parse_file(path):
    """[{name, eng, fields:[(k,v)], notes:[str]}]"""
    out, cur = [], None
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if line.startswith('### '):
            head = line[4:].strip().rstrip('🆕').strip()
            if SKIP_HEAD.search(head):
                cur = None
                continue
            m = re.match(r'^(.*?)\s*[（(]([^()（）]+)[)）]\s*$', head)
            name, eng = (m.group(1), m.group(2)) if m else (head, '')
            cur = {'name': name.strip(), 'eng': eng.strip(), 'fields': [], 'notes': []}
            out.append(cur)
        elif line.startswith('## ') or line.startswith('# ') or line.startswith('---'):
            cur = None
        elif cur is not None:
            m = re.match(r'^- \*\*([^*]+)\*\*\s*[:：]\s*(.*)$', line)
            if m:
                cur['fields'].append((m.group(1).strip(), m.group(2).strip()))
            elif line.strip().startswith('- '):
                cur['notes'].append(line.strip()[2:])
            elif line.strip() and not line.strip().startswith('>'):
                cur['notes'].append(line.strip())
    return [d for d in out if d['fields'] or d['notes']]


def parse_resistant(path):
    """제4급 §C 표(| 균 | 병원체 | 주요 감염 | 특징 |) → 4종 항목."""
    txt = open(path, encoding='utf-8').read()
    sec = re.search(r'^## C\..*?(?=^## D\.)', txt, re.M | re.S)
    if not sec:
        return []
    common = '건강인에겐 대개 무해하나 면역저하 입원환자에서 문제. 잠복기 미확인. 예방 핵심은 손위생·접촉주의·환경소독.'
    out = []
    for row in re.findall(r'^\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|\s*$', sec.group(0), re.M):
        code = re.sub(r'\*|\s', '', row[0])
        if code not in RESIST_NAMES:
            continue
        out.append({
            'name': RESIST_NAMES[code], 'eng': code, 'notes': [],
            'fields': [
                ('급수/신고', '제4급 · 표본감시(의료관련감염병)'),
                ('병원체', row[1].strip()),
                ('주요 감염', row[2].strip()),
                ('특징', row[3].strip()),
                ('예방', common),
                ('치료', '감수성 검사 기반 선택(제한적; MRAB는 콜리스틴 등 최후 약제)'),
            ],
        })
    return out


def load_aliases():
    """canonical명 → [별칭 문자열]"""
    j = json.load(open(os.path.join(SRC, '별칭사전.json'), encoding='utf-8'))
    m = {}
    for e in j.get('entries', []):
        names = [a.get('name', '') for a in e.get('aliases', []) if a.get('name')]
        if names:
            m[e['canonical']] = names
        if e.get('english'):
            m.setdefault(e['canonical'], names)
    return m, {e['canonical']: e.get('english', '') for e in j.get('entries', [])}


def build():
    alias_map, eng_map = load_aliases()
    diseases = []
    for gnum, glabel, fname, gdesc in GRADES:
        parsed = parse_file(os.path.join(SRC, fname))
        if gnum == '4':
            parsed += parse_resistant(os.path.join(SRC, fname))
        for d in parsed:
            d['grade'] = gnum
            base = re.sub(r'\s*감염증$|\s*\(.*\)$', '', d['name'])
            als = alias_map.get(d['name']) or alias_map.get(base) or []
            d['aliases'] = als
            if not d['eng']:
                d['eng'] = eng_map.get(d['name'], '')
            diseases.append(d)
    counts = {g: sum(1 for d in diseases if d['grade'] == g) for g, *_ in GRADES}
    print('수록:', counts, '합계', len(diseases))

    cards = []
    for d in diseases:
        g = d['grade']
        hay = ' '.join([d['name'], d['eng'], *d['aliases']]).lower().replace(' ', '')
        patho = next((v for k, v in d['fields'] if '병원체' in k), '')
        patho_txt = re.sub(r'\*', '', patho)
        if len(patho_txt) > 46:
            patho_txt = patho_txt[:45] + '…'
        rows = ''.join(
            f'<div class="fr"><dt>{H.escape(k)}</dt><dd>{md_inline(v)}</dd></div>'
            for k, v in d['fields'])
        notes = ''.join(f'<p class="nt">{md_inline(n)}</p>' for n in d['notes'])
        alias_html = (f'<div class="als">옛 이름·별칭: {H.escape(" · ".join(d["aliases"]))}</div>'
                      if d['aliases'] else '')
        eng = f'<span class="eng">{H.escape(d["eng"])}</span>' if d['eng'] else ''
        cards.append(
            f'<details class="dz" data-g="{g}" data-s="{H.escape(hay)}">'
            f'<summary><span class="gb g{g}">{g}급</span>'
            f'<span class="nm">{H.escape(d["name"])}</span>{eng}'
            f'<span class="pv">{H.escape(patho_txt)}</span></summary>'
            f'<div class="bd"><dl>{rows}</dl>{notes}{alias_html}</div></details>')

    chips = ''.join(
        f'<button class="chip" data-g="{g}" title="{H.escape(desc)}">{lab} '
        f'<span class="n num">{counts[g]}</span></button>'
        for g, lab, _, desc in GRADES)
    grade_notes = ''.join(
        f'<li><b>{lab}</b> — {H.escape(desc)}</li>' for g, lab, _, desc in GRADES)

    page = PAGE_TMPL
    page = page.replace('__CARDS__', '\n'.join(cards))
    page = page.replace('__CHIPS__', chips)
    page = page.replace('__TOTAL__', str(len(diseases)))
    page = page.replace('__GRADE_NOTES__', grade_notes)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(page)
    print('→', os.path.relpath(OUT, ROOT), f'{os.path.getsize(OUT):,}B')


PAGE_TMPL = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>감염병 질병정보 도감</title>
<style>
  :root{
    --ground:#F5F7F6; --surface:#FFFFFF; --surface-2:#EEF2F0;
    --ink:#16211D; --muted:#5B6B65; --faint:#8A9793;
    --line:#DCE4E1; --line-strong:#C4D0CB;
    --accent:#0E6E63; --accent-soft:#D7ECE8; --accent-ink:#0A4A43;
    --c1:#B23A3A; --c2:#C7712B; --c3:#B8942A; --c4:#2F7D8C;
    --shadow:0 1px 2px rgba(16,33,29,.05),0 8px 28px rgba(16,33,29,.06);
  }
  @media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
    --ground:#0D1412; --surface:#141E1A; --surface-2:#1B2723;
    --ink:#E7EDEA; --muted:#9DACA6; --faint:#71807A;
    --line:#243330; --line-strong:#32433E;
    --accent:#54B7AA; --accent-soft:#193A35; --accent-ink:#9FE0D7;
    --c1:#E07A7A; --c2:#E0A268; --c3:#D8BE6A; --c4:#6FBECB;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
  }}
  :root[data-theme="dark"]{
    --ground:#0D1412; --surface:#141E1A; --surface-2:#1B2723;
    --ink:#E7EDEA; --muted:#9DACA6; --faint:#71807A;
    --line:#243330; --line-strong:#32433E;
    --accent:#54B7AA; --accent-soft:#193A35; --accent-ink:#9FE0D7;
    --c1:#E07A7A; --c2:#E0A268; --c3:#D8BE6A; --c4:#6FBECB;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);line-height:1.6;letter-spacing:-.01em;
    word-break:keep-all;
    font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',system-ui,-apple-system,sans-serif;}
  .num{font-variant-numeric:tabular-nums}
  a{color:var(--accent-ink);text-decoration:none}
  .wrap{max-width:860px;margin:0 auto;padding:0 20px}
  nav{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--ground) 88%,transparent);
    backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
  nav .in{max-width:860px;margin:0 auto;padding:11px 20px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  nav .brand{font-weight:800;font-size:14px;margin-right:auto}
  nav .brand .dot{color:var(--accent)}
  nav a{font-size:12.5px;color:var(--muted);padding:5px 9px;border-radius:8px;font-weight:600;white-space:nowrap}
  nav a:hover{background:var(--surface-2);color:var(--ink)}
  header{padding:44px 0 10px}
  .eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:700;margin:0 0 12px}
  h1{font-size:clamp(28px,5.5vw,44px);line-height:1.06;margin:0;font-weight:800;letter-spacing:-.03em}
  .thesis{font-size:clamp(14px,2.2vw,16.5px);color:var(--muted);max-width:62ch;margin:14px 0 0}

  .tools{position:sticky;top:47px;z-index:10;background:var(--ground);padding:14px 0 10px;border-bottom:1px solid var(--line)}
  .search{width:100%;font-size:16px;padding:12px 16px;border-radius:12px;border:1.5px solid var(--line-strong);
    background:var(--surface);color:var(--ink);outline:none}
  .search:focus{border-color:var(--accent)}
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
  .chip{font:inherit;font-size:13px;font-weight:700;color:var(--muted);background:var(--surface);
    border:1px solid var(--line-strong);border-radius:999px;padding:6px 13px;cursor:pointer}
  .chip .n{color:var(--faint);font-weight:600}
  .chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
  .chip.on .n{color:#fff9}
  .cnt{margin-left:auto;font-size:12.5px;color:var(--faint)}

  .list{padding:16px 0 8px}
  .dz{background:var(--surface);border:1px solid var(--line);border-radius:14px;margin-bottom:10px;box-shadow:var(--shadow);overflow:hidden}
  .dz[hidden]{display:none}
  .dz summary{display:flex;align-items:center;gap:10px;padding:13px 16px;cursor:pointer;list-style:none;flex-wrap:wrap}
  .dz summary::-webkit-details-marker{display:none}
  .dz summary:hover{background:var(--surface-2)}
  .gb{flex:none;font-size:11.5px;font-weight:800;color:#fff;border-radius:7px;padding:3px 8px;letter-spacing:.02em}
  .g1{background:var(--c1)}.g2{background:var(--c2)}.g3{background:var(--c3)}.g4{background:var(--c4)}
  .nm{font-weight:800;font-size:15.5px}
  .eng{font-size:12.5px;color:var(--faint)}
  .pv{flex-basis:100%;font-size:12.5px;color:var(--muted);padding-left:2px}
  .bd{border-top:1px solid var(--line);padding:14px 18px 16px}
  dl{margin:0}
  .fr{display:grid;grid-template-columns:92px 1fr;gap:10px;padding:5px 0;font-size:14px}
  .fr dt{color:var(--faint);font-weight:700;font-size:12.5px;padding-top:2px}
  .fr dd{margin:0;color:var(--ink)}
  .nt{font-size:13.5px;color:var(--muted);margin:8px 0 0}
  .als{margin-top:10px;font-size:12.5px;color:var(--accent-ink);background:var(--accent-soft);
    border-radius:9px;padding:7px 11px;display:inline-block}
  .empty{display:none;text-align:center;color:var(--faint);padding:40px 0;font-size:14px}

  .legend{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:18px 0}
  .legend h2{font-size:14px;margin:0 0 8px}
  .legend ul{margin:0;padding-left:18px;font-size:13px;color:var(--muted)}
  .legend li{margin:3px 0}
  footer{padding:28px 0 56px;color:var(--faint);font-size:13px;border-top:1px solid var(--line);margin-top:24px}
  footer .maker{margin:0 0 10px;font-size:14px;color:var(--ink)}
  footer .maker a{color:var(--accent-ink)}
  .warn{background:var(--accent-soft);color:var(--accent-ink);border-radius:12px;padding:13px 16px;font-size:13px;margin:14px 0 0}
  @media(max-width:520px){.fr{grid-template-columns:76px 1fr}}
</style>
</head>
<body>
<nav><div class="in">
  <span class="brand">🦠 감염병 자료 아카이브<span class="dot">.</span></span>
  <a href="../">🏠 허브</a><a href="../chronicle/">📜 연대기</a><a href="../checker/">🩺 검사기</a>
</div></nav>

<div class="wrap">
<header>
  <p class="eyebrow">Disease Encyclopedia</p>
  <h1>감염병 질병정보 도감</h1>
  <p class="thesis">법정감염병 <b class="num">__TOTAL__</b>종의 실제 내용 — 병원체·감염경로·잠복기·증상·치료·예방.
  모든 항목은 질병관리청 공식 자료(감염병포털·감염병누리집·국가건강정보포털·관리지침)에서 수집·교차확인했다.
  옛 이름(흑사병·천연두·원숭이두창…)으로도 검색된다.</p>
</header>

<div class="tools">
  <input class="search" id="q" type="search" placeholder="질병 이름·영문·옛 이름 검색 (예: 흑사병, MPOX, 쯔쯔가무시)" autocomplete="off">
  <div class="chips">
    <button class="chip on" data-g="all">전체 <span class="n num">__TOTAL__</span></button>
    __CHIPS__
    <span class="cnt"><span id="shown" class="num">__TOTAL__</span>종 표시</span>
  </div>
</div>

<div class="list" id="list">
__CARDS__
<div class="empty" id="empty">검색 결과가 없습니다. 다른 이름(옛 이름·영문)으로 시도해 보세요.</div>
</div>

<div class="legend">
  <h2>급수별 신고 의무</h2>
  <ul>__GRADE_NOTES__</ul>
  <ul style="margin-top:8px">
    <li>⚠️ 급수·신고 기준은 <b>현행(2026년) 기준</b>이다. 과거 시점의 지위는 <a href="../chronicle/">📜 연대기</a>에서 날짜를 대고 확인할 것.</li>
    <li>'미확인'은 질병관리청 자료에서 확정하지 못한 항목이며 추정하지 않았다.</li>
  </ul>
</div>

<footer>
  <div class="maker">제작: <a href="https://jieumworks.com" target="_blank" rel="noopener"><b>지움웍스</b> jieumworks.com</a> · 2026년 9월</div>
  <div>출처: 감염병누리집 · 감염병포털 · 국가건강정보포털 · 예방접종도우미 · 병원체생물안전정보 · 급수별 대응·관리지침 —
    <a href="https://github.com/soonryu74/disease/tree/claude/infectious-disease-resources-org-kbjcfz/05_%EA%B0%90%EC%97%BC%EB%B3%91_%EC%A7%88%EB%B3%91%EC%A0%95%EB%B3%B4" target="_blank" rel="noopener">원자료(GitHub)</a></div>
  <div class="warn">⚠️ 참고용 정리물입니다. 진단·치료는 반드시 의료진·보건소 확인을 거쳐야 합니다.</div>
</footer>
</div>

<script>
(function(){
  var q=document.getElementById('q'), shown=document.getElementById('shown'),
      empty=document.getElementById('empty'),
      cards=[].slice.call(document.querySelectorAll('.dz')),
      chips=[].slice.call(document.querySelectorAll('.chip')),
      grade='all';
  function norm(s){return s.toLowerCase().replace(/\\s+/g,'');}
  function apply(){
    var t=norm(q.value||''), n=0;
    cards.forEach(function(c){
      var ok=(grade==='all'||c.dataset.g===grade)&&(!t||c.dataset.s.indexOf(t)>-1||norm(c.textContent).indexOf(t)>-1);
      c.hidden=!ok; if(ok)n++;
    });
    shown.textContent=n;
    empty.style.display=n?'none':'block';
  }
  q.addEventListener('input',apply);
  chips.forEach(function(ch){ch.addEventListener('click',function(){
    grade=ch.dataset.g;
    chips.forEach(function(x){x.classList.toggle('on',x===ch);});
    apply();
  });});
})();
</script>
</body>
</html>
'''

if __name__ == '__main__':
    build()
