#!/usr/bin/env python3
"""모든 포털 페이지에 인쇄 스타일과 도구 막대(인쇄·자료받기)를 주입한다.

페이지 템플릿이 제각각이라 각 파일에 손으로 넣으면 곧 어긋난다. 조립 단계에서
한 번에 넣어 모든 쪽이 같게 동작하도록 한다.

인쇄에서 하는 일
 - 내비·도구막대·검색창·필터를 감춘다
 - 어두운 테마여도 흰 종이에 검은 글씨로 강제한다(잉크·가독성)
 - 접힌 <details>(표 보기 등)를 전부 펼친다
 - 카드·패널·표 행이 쪽 경계에서 잘리지 않게 한다
 - 출처·주소·인쇄일을 머리글로 찍는다 — 종이만 돌아다녀도 출처를 잃지 않게
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 제작 크레딧 — 문구와 날짜는 site-config.json 한 곳에서 관리한다.
# 예전에는 열여섯 개 템플릿에 제각각 박혀 있어서, 날짜 한 번 고치려면 열여섯 군데를
# 손대야 했고 문구도 '제작:'과 'Built by' 두 가지로 갈려 있었다.
try:
    _CFG = json.load(open(os.path.join(ROOT, 'site-config.json'), encoding='utf-8'))
except Exception:                                        # noqa: BLE001
    _CFG = {}
CREDIT = _CFG.get('credit') or {}

CREDIT_CSS = """
/* ── 제작 크레딧 — 모든 쪽 맨 아래 공용. 문구는 site-config.json 한 곳에서 관리한다 ──
   쪽마다 제 footer 규칙이 있어서 footer.site-credit 로도 함께 적는다.
   선택자 하나만 두면 그 쪽의 footer{font-size:…} 에 밀린다. */
footer.site-credit, .site-credit{margin:28px 0 0;padding:0 16px 76px;text-align:center;
  font-size:.76rem;line-height:1.6;color:#8a94a0;word-break:keep-all;overflow-wrap:anywhere}
/* 인쇄·자료받기 단추가 오른쪽 아래에 떠 있어서, 끝까지 내리면 크레딧을 가렸다.
   단추 높이만큼 아래를 비워 둔다. 종이에는 단추가 없으니 그 여백을 되돌린다. */
@media print{footer.site-credit, .site-credit{padding-bottom:0}}
footer.site-credit a, .site-credit a{color:inherit;text-decoration:underline;text-underline-offset:2px}
@media print{footer.site-credit, .site-credit{display:block !important;color:#6b7480;margin-top:6mm}}
"""


def credit_html():
    """맨 아래 한 줄. 본문이 끝난 뒤, 기존 안내 문구보다 더 아래에 놓는다."""
    k = CREDIT
    if not k:
        return ''
    return ('<footer class="site-credit">'
            f'{k.get("role", "")} {k.get("name", "")} · '
            f'<a href="{k.get("url", "")}" target="_blank" rel="noopener">{k.get("site", "")}</a>'
            f' · {k.get("date", "")}</footer>')


PRINT_CSS = """
/* ── 인쇄 ─────────────────────────────────────────────────────────── */
.printonly{display:none}
@page{margin:14mm 12mm}
@media print{
  /* 화면 전용 요소 감추기 */
  nav, .pagetools, .search, .chips, .tools, button, .foot-links,
  details.tbl > summary, .empty{display:none !important}
  /* 어두운 테마여도 종이에는 흰 바탕·검은 글씨로 */
  :root, :root[data-theme="dark"], :root:not([data-theme="light"]){
    --ground:#fff !important; --surface:#fff !important; --surface-2:#f2f2f2 !important;
    --ink:#111 !important; --muted:#333 !important; --faint:#555 !important;
    --line:#ccc !important; --line-strong:#999 !important;
    --grid:#ddd !important; --shadow:none !important;
    color-scheme: light !important;
  }
  body{background:#fff !important;color:#111 !important;font-size:10.5pt;line-height:1.45}
  .wrap{max-width:100% !important;padding:0 !important}
  header{padding:0 0 6mm !important}
  h1{font-size:20pt !important}
  h2{font-size:13pt !important}
  section{padding:4mm 0 0 !important}
  .card,.panel,.rk,.brk,.find,.dz,.dis,.f,.tile{
    box-shadow:none !important;break-inside:avoid;page-break-inside:avoid}
  h1,h2,h3{break-after:avoid;page-break-after:avoid}
  tr,img,svg{break-inside:avoid;page-break-inside:avoid}
  thead{display:table-header-group}
  /* 접힌 자료를 펼쳐서 종이에 담기 */
  details.tbl,details{border:none !important}
  details.tbl .tw{padding:0 !important;overflow:visible !important}
  .tw{overflow:visible !important}
  table{font-size:8.5pt !important;width:100% !important}
  th,td{padding:2px 4px !important}
  th:first-child,td:first-child{position:static !important}
  a{color:#111 !important;text-decoration:none}
  .printonly{display:block !important}
  .printhead{border-bottom:1.5px solid #999;padding-bottom:3mm;margin-bottom:5mm;
    font-size:9pt;color:#333}
  .printhead b{color:#111}
  .printfoot{border-top:1px solid #ccc;padding-top:3mm;margin-top:6mm;font-size:8.5pt;color:#555}
}
/* ── 화면용 도구 막대 ─────────────────────────────────────────────── */
.pagetools{position:fixed;right:16px;bottom:16px;z-index:60;display:flex;gap:8px;flex-wrap:wrap}
.pagetools a,.pagetools button{
  font:inherit;font-size:13px;font-weight:700;cursor:pointer;
  background:var(--surface);color:var(--accent-ink);
  border:1px solid var(--line-strong);border-radius:999px;padding:9px 15px;
  box-shadow:0 2px 10px rgba(0,0,0,.12);display:inline-flex;align-items:center;gap:6px}
.pagetools a:hover,.pagetools button:hover{background:var(--surface-2)}
@media(max-width:520px){.pagetools{right:10px;bottom:10px}
  .pagetools a,.pagetools button{padding:8px 12px;font-size:12.5px}}
"""

PRINT_JS = """
<script>
/* 인쇄 전에 접힌 자료를 펼치고, 인쇄 후 원래대로 되돌린다 */
(function(){
  var opened = [];
  function expand(){
    opened = [];
    document.querySelectorAll('details').forEach(function(d){
      if (!d.open){ opened.push(d); d.open = true; }
    });
  }
  function restore(){ opened.forEach(function(d){ d.open = false; }); opened = []; }
  window.addEventListener('beforeprint', expand);
  window.addEventListener('afterprint', restore);
  var btn = document.getElementById('btnPrint');
  if (btn) btn.addEventListener('click', function(){ expand(); window.print(); });
  var ph = document.getElementById('printhead');
  if (ph){
    var d = new Date();
    var pad = function(n){ return String(n).padStart(2, '0'); };
    ph.querySelector('.pdate').textContent =
      d.getFullYear() + '.' + pad(d.getMonth()+1) + '.' + pad(d.getDate()) + ' 인쇄';
    ph.querySelector('.purl').textContent = location.href.replace(/^https?:\\/\\//, '');
  }
})();
</script>
"""


# ── 공통 상단 메뉴 ─────────────────────────────────────────────────────
# 페이지마다 제각각이던 내비를 조립 단계에서 하나로 통일한다. 페이지 자체 <nav>는 감춘다.
# 스무 개를 한 줄에 늘어놓던 것을 다섯 가지 '하려는 일' 아래로 묶는다. 주소는 하나도 바꾸지 않는다 —
# 같은 페이지가 두 묶음에 들어갈 수 있다(검역관리지역은 '오늘'이기도 하고 '분석'이기도 하다).
NAV_GROUPS = [
    ('today', '📡', '오늘의 상황', [
        ('daily/', '감염병 상황판', 'WHO·CDC·질병관리청 새 소식'),
        ('flu/', '인플루엔자 감시', '아형·백신 정합성·주간 검출'),
        ('inflow/', '해외유입 지도', '지정국에서 실제로 얼마나 들어오나'),
        ('quarantine/', '검역관리지역', '지금 Q-CODE를 내야 하는 나라'),
    ]),
    ('disease', '🚑', '질병·현장대응', [
        ('dogam/', '감염병 도감', '91종 법정감염병 정보'),
        ('field/', '현장 대응카드', '신고·격리·잠복기·지침 한 화면'),
        ('guides/', '관리지침', '1,727 계열 · 2,347건'),
        ('vaccine/', '예방접종', '접종률과 집단면역 임계치'),
        ('lab/', '진단검사', '병원체 검출 감시'),
        ('pathogen/', '병원체 도감', '형태·분류'),
    ]),
    ('basis', '⚖', '제도·근거', [
        ('chronicle/', '감염병 연대기', '급수·감시체계 변천 타임머신'),
        ('law/', '감염병예방법 70년', '법령 연혁 192건'),
        ('whitepaper/', '백서', '질병관리청 백서 19판'),
        ('guides/', '지침 아카이브', '연도별 지침·서식'),
        ('hall/', '연도별 전시관', '해마다 무엇이 달라졌나'),
        ('brief/', '검토 보고', '위험평가 도구 검토'),
    ]),
    ('analysis', '🧪', '분석·실험', [
        ('checker/', '단절점 검사기', '두 연도를 비교해도 되나'),
        ('cross/', '교차검증', '신고 수와 검출 수 맞대기'),
        ('quarantine/', '검역관리지역', '지정 이력과 단절점'),
        ('inflow/', '해외유입 분석', '직항·입국자·유입 신고'),
        ('policy/', '검역 정책실험실', '나라를 넣고 빼면 무엇이 새나'),
        ('sim/', '유행 시뮬레이터', 'R₀·격리·접종 손잡이'),
    ]),
    ('data', '⬇', '데이터', [
        ('data/', '데이터 다운로드', 'CSV · JSON 27개 파일'),
        ('data/#use', '데이터 출처·이용 안내', '어디서 왔고 어떻게 써야 하나'),
        ('https://github.com/soonryu74/disease', '원자료 저장소 (GitHub)', '수집 코드와 원본'),
        ('https://github.com/soonryu74/disease/commits', '오류·수정 기록', '변경 이력'),
    ]),
]
SEARCH_HREF = 'search/'
# 예전 코드(상황판 수집기 등)가 평면 목록을 참조할 수 있어 남겨 둔다
NAV_ITEMS = [('', '🏠', '허브')] + [(h, ic, l) for _, ic, _, items in NAV_GROUPS for h, l, _ in items if '://' not in h]

NAV_CSS = """
/* ── 공통 메뉴 ─────────────────────────────────────────────────────── */
nav:not(.gnav){display:none !important}
.gnav{position:sticky;top:0;z-index:70;background:color-mix(in srgb,var(--ground,#F5F7F6) 92%,transparent);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line,#DCE4E1);
  font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',system-ui,sans-serif;letter-spacing:-.01em}
.gnav *{box-sizing:border-box}
.gnav .gin{max-width:1100px;margin:0 auto;padding:6px 14px;display:flex;align-items:center;gap:6px;position:relative}
.gnav .gbrand{font-weight:800;font-size:14px;color:var(--ink,#16211D);white-space:nowrap;margin-right:8px;text-decoration:none;flex:none;padding:6px 0}
.gnav .gbrand i{color:var(--accent,#0E6E63);font-style:normal}
.gnav .gskip{position:absolute;left:-9999px;top:0;background:var(--accent,#0E6E63);color:#fff;padding:8px 12px;border-radius:8px;z-index:80}
.gnav .gskip:focus{left:14px;top:6px}
.gnav .gmenu{display:flex;align-items:center;gap:2px;flex:1;min-width:0;flex-wrap:wrap}
.gnav .gg{position:relative}
.gnav .gt{font:inherit;font-size:13px;font-weight:700;color:var(--muted,#5B6B65);background:none;border:0;border-radius:8px;
  padding:7px 10px;cursor:pointer;white-space:nowrap;line-height:1.4;min-height:36px}
.gnav .gt:hover,.gnav .gg.open .gt{background:var(--surface-2,#EEF2F0);color:var(--ink,#16211D)}
.gnav .gt.on{color:var(--accent-ink,#0A4A43);box-shadow:inset 0 -2px 0 var(--accent,#0E6E63);border-radius:8px 8px 0 0}
.gnav .gt .car{font-size:10px;opacity:.6;margin-left:3px}
.gnav .gd{display:none;position:absolute;left:0;top:calc(100% + 4px);min-width:250px;background:var(--surface,#fff);
  border:1px solid var(--line,#DCE4E1);border-radius:12px;padding:6px;box-shadow:0 10px 30px rgba(16,33,29,.14);z-index:75}
.gnav .gg.open .gd{display:block}
.gnav a.gi{display:block;font-size:13.5px;color:var(--ink,#16211D);padding:8px 10px;border-radius:8px;font-weight:600;
  text-decoration:none;line-height:1.35;min-height:44px}
.gnav a.gi small{display:block;font-size:11.5px;color:var(--muted,#5B6B65);font-weight:500;margin-top:1px}
.gnav a.gi:hover,.gnav a.gi:focus-visible{background:var(--surface-2,#EEF2F0)}
.gnav a.gi.on{background:var(--accent-soft,#D7ECE8);color:var(--accent-ink,#0A4A43)}
.gnav a.gi.on small{color:var(--accent-ink,#0A4A43)}
.gnav .gsearch{margin-left:auto;font-size:13px;font-weight:800;color:#fff;background:var(--accent,#0E6E63);border-radius:999px;
  padding:7px 14px;text-decoration:none;white-space:nowrap;flex:none;min-height:36px;display:inline-flex;align-items:center;gap:6px}
.gnav .gsearch:hover{filter:brightness(1.08)}
.gnav .gburger{display:none;font:inherit;font-size:13px;font-weight:700;background:var(--surface,#fff);border:1px solid var(--line-strong,#C4D0CB);
  border-radius:8px;padding:7px 11px;cursor:pointer;color:var(--ink,#16211D);min-height:40px;margin-left:auto}
.gnav :focus-visible{outline:2px solid var(--accent,#0E6E63);outline-offset:2px}
@media (hover:hover) and (min-width:901px){
  .gnav .gg:hover .gd,.gnav .gg:focus-within .gd{display:block}
}
@media (max-width:900px){
  /* 좁은 화면: 상표 + 검색 + ☰. 묶음은 아코디언으로 펼친다. 자료를 가리지 않도록 따라다니지 않는다. */
  .gnav{position:static}
  .gnav .gin{flex-wrap:wrap;padding:6px 12px}
  .gnav .gbrand{font-size:13px;margin-right:auto}
  .gnav .gsearch{margin-left:0;padding:6px 12px;font-size:12.5px;min-height:38px}
  .gnav .gburger{display:inline-block;margin-left:0}
  .gnav .gmenu{display:none;flex-direction:column;align-items:stretch;flex-basis:100%;padding:6px 0 4px;gap:4px}
  .gnav.open .gmenu{display:flex}
  .gnav .gg{border:1px solid var(--line,#DCE4E1);border-radius:10px;background:var(--surface,#fff)}
  .gnav .gt{width:100%;text-align:left;font-size:14px;min-height:44px;border-radius:10px}
  .gnav .gt.on{box-shadow:none;background:var(--accent-soft,#D7ECE8)}
  .gnav .gd{display:none;position:static;min-width:0;border:0;border-top:1px solid var(--line,#DCE4E1);border-radius:0 0 10px 10px;box-shadow:none;padding:4px}
  .gnav .gg.open .gd{display:block}
}
@media (prefers-reduced-motion:reduce){.gnav *{transition:none !important}}

/* ── 출처 성격 배지 — 공식 원문인지, 우리가 엮은 것인지, 계산한 것인지 ──────── */
.bdg{display:inline-block;font-size:11px;font-weight:800;border-radius:999px;padding:2px 8px;white-space:nowrap;letter-spacing:-.01em}
.bdg.official{background:var(--accent-soft,#D7ECE8);color:var(--accent-ink,#0A4A43)}
.bdg.archive{background:var(--info-soft,#DCEDF1);color:var(--info-ink,#1B5561)}
.bdg.analysis{background:var(--model-soft,#E7E0F2);color:var(--model-ink,#4A3368)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .bdg.archive{background:#17333A;color:#9FD8E2}
  :root:not([data-theme="light"]) .bdg.analysis{background:#2A2338;color:#CDBBEC}}
"""

NAV_JS = """<script>
(function(){
  var nav=document.querySelector('nav.gnav'); if(!nav) return;
  var burger=nav.querySelector('.gburger');
  function closeAll(except){ nav.querySelectorAll('.gg.open').forEach(function(g){ if(g!==except){ g.classList.remove('open'); g.querySelector('.gt').setAttribute('aria-expanded','false'); } }); }
  nav.querySelectorAll('.gt').forEach(function(t){
    t.addEventListener('click',function(){ var g=t.parentNode, open=!g.classList.contains('open'); closeAll(g); g.classList.toggle('open',open); t.setAttribute('aria-expanded',open?'true':'false'); });
  });
  if(burger){ burger.addEventListener('click',function(){ var open=!nav.classList.contains('open'); nav.classList.toggle('open',open); burger.setAttribute('aria-expanded',open?'true':'false'); burger.textContent=open?'✕ 닫기':'☰ 메뉴'; if(open){ var on=nav.querySelector('.gt.on'); if(on){ on.parentNode.classList.add('open'); on.setAttribute('aria-expanded','true'); } } }); }
  document.addEventListener('click',function(e){ if(!nav.contains(e.target)) closeAll(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'){ closeAll(); if(nav.classList.contains('open')&&burger) burger.click(); } });
})();
</script>"""


def nav_html(up, current):
    """current: 포털 루트 기준 폴더명('' = 허브). 그 페이지가 든 묶음과 항목에 on을 단다."""
    cur = (current or '').rstrip('/')
    groups = []
    for gid, icon, label, items in NAV_GROUPS:
        links, g_on = [], False
        for href, name, desc in items:
            ext = '://' in href
            on = (not ext) and href.split('#')[0].rstrip('/') == cur and cur != ''
            g_on = g_on or on
            url = href if ext else up + href
            extra = ' target="_blank" rel="noopener"' if ext else ''
            cls = ' on' if on else ''
            cur_attr = ' aria-current="page"' if on else ''
            links.append(f'<a class="gi{cls}" href="{url}"{extra}{cur_attr}>{name}<small>{desc}</small></a>')
        groups.append(f'<div class="gg"><button class="gt{" on" if g_on else ""}" type="button" aria-expanded="false" aria-haspopup="true">'
                      f'{icon} {label}<span class="car">▾</span></button><div class="gd">{"".join(links)}</div></div>')
    return (f'<nav class="gnav" aria-label="전체 메뉴"><div class="gin">'
            f'<a class="gskip" href="#main">본문으로 건너뛰기</a>'
            f'<a class="gbrand" href="{up}./">🦠 감염병 자료 아카이브<i>.</i></a>'
            f'<a class="gsearch" href="{up}{SEARCH_HREF}" title="감염병명·국가·연도·지침·법령 검색">🔍 검색</a>'
            f'<button class="gburger" type="button" aria-expanded="false" aria-controls="gmenu">☰ 메뉴</button>'
            f'<div class="gmenu" id="gmenu">{"".join(groups)}</div>'
            f'</div></nav>' + NAV_JS)


def inject_nav(path, depth, current):
    s = open(path, encoding='utf-8').read()
    # 이미 있으면 걷어내고 다시 넣는다 — 메뉴 항목이 바뀌면 모든 쪽이 같이 바뀌어야 한다
    s = re.sub(r'\n?<nav class="gnav"[^>]*>.*?</nav>(?:<script>.*?</script>)?', '', s, flags=re.S)
    # 예전 판의 메뉴 CSS(문구가 달라도)까지 걷어낸다. 메뉴 CSS는 언제나 첫 </style> 바로 앞에 있다.
    # 앞뒤 줄바꿈까지 같이 걷어내야 한다. 예전에는 </style> 앞 줄바꿈을 남겨 두고
    # 그 앞에 또 넣어서, 다시 빌드할 때마다 빈 줄이 한 줄씩 늘었다 —
    # 내용은 그대로인데 22쪽 전부가 바뀐 것으로 잡히던 원인이다.
    s = re.sub(r'\n?/\* ── 공통 메뉴[\s\S]*?(?=</style>)', '', s, count=1)
    if '</style>' in s:
        s = s.replace('</style>', NAV_CSS + '\n</style>', 1)
    else:
        s = s.replace('</head>', f'<style>{NAV_CSS}</style>\n</head>', 1)
    html = nav_html('../' * depth, current)
    # 인쇄 머리글 뒤(= 본문 맨 앞)에 둔다. 머리글이 없으면 <body> 뒤.
    idx = s.find('</div>', s.find('id="printhead"')) if 'id="printhead"' in s else -1
    if idx >= 0:
        cut = idx + len('</div>')
        s = s[:cut] + '\n' + html + s[cut:]
    else:
        body = re.search(r'<body[^>]*>', s)
        s = (s[:body.end()] + '\n' + html + s[body.end():]) if body else html + s
    # 건너뛰기 링크가 닿을 곳 — 본문 첫 <header>나 첫 <main>에 id를 단다(없으면 그대로 둔다)
    if 'id="main"' not in s:
        s = re.sub(r'<(main|header)(?![^>]*\bid=)', r'<\1 id="main"', s, count=1)
    open(path, 'w', encoding='utf-8').write(s)
    return True


def tools_html(data_href='data/', home='./'):
    return (f'<div class="pagetools">'
            f'<button id="btnPrint" type="button" title="이 페이지를 인쇄하거나 PDF로 저장">🖨 인쇄</button>'
            f'<a href="{data_href}" title="이 사이트가 쓰는 원자료 내려받기">⬇ 자료받기</a>'
            f'</div>')


def printhead_html(title):
    site = CREDIT.get('site', 'jieumworks.com')
    return ('<div class="printonly printhead" id="printhead">'
            f'<b>{title}</b> — 감염병 자료 아카이브 · 제작 {site}<br>'
            '<span class="purl"></span> · <span class="pdate"></span> · '
            '원자료: 질병관리청 · 법제처'
            '</div>')


# 예전 판 크레딧 — 쪽마다 문구·자리가 달랐다. 새로 붙이기 전에 걷어낸다.
# 두 가지 모양뿐이라 그 둘만 정확히 집어낸다. 다른 글은 건드리지 않는다.
_OLD_CREDIT = (
    re.compile(r'\s*<div class="maker">제작:.*?jieumworks\.com.*?</div>', re.S),
    re.compile(r'\s*<div style="margin-top:6px">Built by\s*<a[^>]*jieumworks\.com.*?</div>', re.S),
)
_CREDIT_RE = re.compile(r'\s*<footer class="site-credit">.*?</footer>', re.S)


def inject_credit(path):
    """맨 아래 제작 크레딧을 붙인다. 이미 있으면 새 문구로 갈아 끼운다.

    본문이 끝난 자리(</body> 바로 앞)에 두므로 기존 안내 문구보다 늘 아래에 온다.
    """
    html = credit_html()
    if not html:
        return False
    s = open(path, encoding='utf-8').read()
    before = s
    for rx in _OLD_CREDIT:
        s = rx.sub('', s)
    s = _CREDIT_RE.sub('', s)
    if '</body>' in s:
        s = s.replace('</body>', html + '\n</body>', 1)
    else:
        s = s.rstrip() + '\n' + html + '\n'
    if s == before:
        return False
    open(path, 'w', encoding='utf-8').write(s)
    return True


SUMMARY_CSS = """
/* ── 쉽게 말하면 — 쪽 첫머리에 두는 두세 문장 ─────────────────────── */
.plainsum{background:var(--accent-soft,#D7ECE8);color:var(--accent-ink,#0A4A43);
  border-radius:14px;padding:14px 17px;margin:18px 0 0;font-size:14.5px;line-height:1.75;
  word-break:keep-all;overflow-wrap:anywhere}
.plainsum b{display:block;font-size:12px;letter-spacing:.06em;opacity:.8;margin-bottom:5px}
.plainsum p{margin:0}
.plainsum p+p{margin-top:3px}
@media print{.plainsum{background:#f2f2f2 !important;color:#111 !important;break-inside:avoid}}
"""

TERMS_CSS = """
/* ── 쉬운 말 풀이 — 어려운 낱말이 처음 나온 자리에 뜻을 단다 ────────── */
.plainterm{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:help;
  border-bottom:1px dashed currentColor;opacity:.98}
.plainterm::after{content:'뜻';font-size:.62em;vertical-align:.5em;margin-left:1px;opacity:.75;
  font-weight:700;letter-spacing:0}
.plainterm[aria-expanded="true"]{background:var(--accent-soft,#D7ECE8)}
.glpop{position:absolute;z-index:90;max-width:min(320px,calc(100vw - 28px));
  background:var(--surface,#fff);color:var(--ink,#16211D);border:1px solid var(--line-strong,#C4D0CB);
  border-radius:12px;padding:12px 14px;box-shadow:0 8px 28px rgba(0,0,0,.18);
  font-size:13.5px;line-height:1.65;font-weight:400;text-align:left;word-break:keep-all}
.glpop b{display:block;font-size:14px;margin-bottom:4px}
.glpop .more{display:block;margin-top:6px;font-size:12.5px;color:var(--muted,#5B6B65)}
details.glbox{margin:22px 0 0;border:1px solid var(--line,#DCE4E1);border-radius:12px;
  background:var(--surface-2,#EEF2F0)}
details.glbox>summary{cursor:pointer;list-style:none;padding:12px 15px;font-size:13.5px;font-weight:700;
  min-height:44px;display:flex;align-items:center;gap:6px}
details.glbox>summary::-webkit-details-marker{display:none}
details.glbox>summary::after{content:'▾';font-size:10px;opacity:.7}
details.glbox[open]>summary::after{content:'▴'}
details.glbox dl{margin:0;padding:0 15px 14px}
details.glbox dt{font-size:13.5px;font-weight:700;margin-top:10px}
details.glbox dd{margin:2px 0 0;font-size:13px;line-height:1.7;color:var(--muted,#5B6B65);word-break:keep-all}
details.glbox dd i{font-style:normal;display:block;margin-top:2px;font-size:12.5px;opacity:.85}
@media print{.plainterm{border-bottom:0}.plainterm::after{display:none}.glpop{display:none}
  details.glbox{break-inside:avoid}details.glbox dl{display:block !important}}
"""


def summary_html(current):
    """이 쪽이 무엇인지 두세 문장으로. 기존 머리글은 그대로 두고 그 아래에 얹는다."""
    try:
        from plain_summaries import SUMMARIES
    except ImportError:
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        from plain_summaries import SUMMARIES
    lines = SUMMARIES.get(current)
    if not lines:
        return ''
    body = ''.join(f'<p>{ln}</p>' for ln in lines)
    return f'<div class="plainsum"><b>쉽게 말하면</b>{body}</div>'


_SUM_RE = re.compile(r'\s*<div class="plainsum">.*?</div>', re.S)


def inject_summary(path, current):
    """머리글 바로 뒤에 놓는다. 머리글이 없으면 첫 제목 뒤에 놓는다."""
    html = summary_html(current)
    if not html:
        return False
    s = open(path, encoding='utf-8').read()
    before = s
    s = _SUM_RE.sub('', s)
    m = re.search(r'</header>', s)
    if m:
        s = s[:m.end()] + '\n' + html + s[m.end():]
    else:
        m = re.search(r'</h1>', s)
        if not m:
            return False
        s = s[:m.end()] + '\n' + html + s[m.end():]
    if s == before:
        return False
    open(path, 'w', encoding='utf-8').write(s)
    return True


def terms_js():
    """쪽마다 어려운 낱말 첫 자리에만 뜻을 달고, 맨 아래에 그 쪽에 나온 말만 모은다.

    본문 글자는 바꾸지 않는다 — 화면에서 감싸기만 한다. 그래서 자료·통계에는 아무 영향이 없다.
    """
    try:
        from plain_glossary import TERMS, ORDER
    except ImportError:
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        from plain_glossary import TERMS, ORDER
    data = json.dumps([[t, TERMS[t][0], TERMS[t][1]] for t in ORDER], ensure_ascii=False)
    return """<script>
/* 쉬운 말 풀이 — scripts/plain_glossary.py 한 곳에서 관리한다 */
(function(){
  var T = __TERMS__;
  var SKIP = {SCRIPT:1, STYLE:1, TEXTAREA:1, INPUT:1, SELECT:1, OPTION:1, CODE:1, PRE:1,
              SVG:1, CANVAS:1, MATH:1};
  var left = {}, found = [], DEF = {}, lastSig = null;
  T.forEach(function(x){ left[x[0]] = x; DEF[x[0]] = [x[1], x[2]]; });

  function skippable(n){
    for (var a = n.parentNode; a && a !== document.body; a = a.parentNode){
      if (a.nodeType !== 1) continue;
      /* SVG 안쪽은 건드리지 않는다. 차트 글자에 단추를 넣으면 그려지지 않는다.
         SVG 요소의 tagName 은 소문자라(svg, text, g) 대문자로 맞춰 본다. */
      if (SKIP[String(a.tagName).toUpperCase()]) return true;
      var c = a.className;
      if (typeof c === 'string' && /\\b(plainterm|glpop|glbox|gnav|printonly|pagetools|site-credit)\\b/.test(c)) return true;
      if (a.tagName === 'BUTTON' || a.hasAttribute('aria-hidden')) return true;
    }
    return false;
  }

  function wrap(node, term, def, more){
    var i = node.nodeValue.indexOf(term);
    if (i < 0) return false;
    var after = node.splitText(i);
    after.nodeValue = after.nodeValue.slice(term.length);
    var btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'plainterm'; btn.textContent = term;
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', term + ' — 뜻 보기');
    btn.onclick = function(e){ e.preventDefault(); e.stopPropagation(); show(btn, term, def, more); };
    node.parentNode.insertBefore(btn, after);
    found.push([term, def, more]);
    return true;
  }

  var pop = null;
  function close(){ if (pop){ pop.remove(); pop = null; }
    document.querySelectorAll('.plainterm[aria-expanded="true"]').forEach(function(b){ b.setAttribute('aria-expanded','false'); }); }
  function show(btn, term, def, more){
    var open = btn.getAttribute('aria-expanded') === 'true';
    close(); if (open) return;
    btn.setAttribute('aria-expanded', 'true');
    pop = document.createElement('span');
    pop.className = 'glpop'; pop.setAttribute('role', 'tooltip');
    pop.innerHTML = '<b></b><span></span>' + (more ? '<span class="more"></span>' : '');
    pop.querySelector('b').textContent = term;
    pop.querySelectorAll('span')[0].textContent = def;
    if (more) pop.querySelector('.more').textContent = more;
    document.body.appendChild(pop);
    var r = btn.getBoundingClientRect(), w = pop.offsetWidth;
    var x = Math.min(Math.max(8, r.left + scrollX), scrollX + innerWidth - w - 8);
    pop.style.left = x + 'px';
    pop.style.top = (r.bottom + scrollY + 6) + 'px';
  }
  document.addEventListener('click', function(e){ if (!e.target.closest('.plainterm,.glpop')) close(); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') close(); });
  addEventListener('resize', close);

  /* 쪽이 제 내용을 다 그린 뒤에 단다. 먼저 달면 나중 렌더링이 주석을 지워,
     본문에는 없는 말이 아래 목록에만 남는 일이 생긴다(유입 지도에서 그랬다). */
  function pass(){
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    var nodes = [], n;
    while ((n = walker.nextNode())) if (n.nodeValue.trim() && !skippable(n)) nodes.push(n);
    for (var i = 0; i < nodes.length; i++){
      for (var k = 0; k < T.length; k++){
        var t = T[k][0];
        if (!left[t]) continue;
        if (wrap(nodes[i], t, T[k][1], T[k][2])){ delete left[t]; }
      }
    }
  }
  function live(){
    var m = {};
    document.querySelectorAll('.plainterm').forEach(function(b){ m[b.textContent] = 1; });
    return m;
  }
  function go(){
    /* 아직 안 달린 말만 다시 찾는다. 쪽이 제 내용을 다시 그리면서 주석을 지워도
       다음 차례에 되살아난다. */
    var on = live();
    left = {};
    T.forEach(function(x){ if (!on[x[0]]) left[x[0]] = x; });
    pass();
    build();
  }
  /* 쪽이 제 내용을 다시 그릴 때마다 주석이 지워질 수 있다(유입 지도의 범례가 그렇다).
     DOM 이 바뀌면 잠깐 기다렸다가 다시 단다. 달 것이 없으면 아무 일도 하지 않으므로 곧 잠잠해진다. */
  var timer = null;
  function start(){
    go();
    var runs = 0, mo = new MutationObserver(function(){
      clearTimeout(timer);
      timer = setTimeout(function(){
        go();
        /* 늘 다시 그리는 쪽(지구본)에서 끝없이 돌지 않게 횟수를 막아 둔다.
           목록이 그대로면 build 가 아무것도 안 하므로 보통은 금방 잠잠해진다. */
        if (++runs >= 30) mo.disconnect();
      }, 400);
    });
    mo.observe(document.body, {childList: true, subtree: true});
  }
  if (document.readyState === 'complete') setTimeout(start, 0);
  else addEventListener('load', function(){ setTimeout(start, 0); });

  function build(){
  /* 목록은 화면에 실제로 달려 있는 주석에서 바로 만든다.
     따로 모아 둔 배열을 쓰면, 쪽이 다시 그려져 주석이 지워졌을 때
     본문에는 없는 말이 목록에만 남는다. */
  var seen = {};
  found = [];
  document.querySelectorAll('.plainterm').forEach(function(b){
    var t = b.textContent;
    if (seen[t] || !DEF[t]) return;
    seen[t] = 1; found.push([t, DEF[t][0], DEF[t][1]]);
  });
  /* 목록이 그대로면 손대지 않는다. 손댈 때마다 DOM 이 바뀌어 관찰이 다시 돌면 끝이 없다. */
  var sig = found.map(function(f){ return f[0]; }).sort().join('|');
  if (sig === lastSig) return;
  lastSig = sig;
  var old = document.querySelector('details.glbox');
  var wasOpen = old && old.open;
  if (old) old.remove();
  if (!found.length) return;
  found.sort(function(a, b){ return a[0].localeCompare(b[0], 'ko'); });
  var box = document.createElement('details');
  box.className = 'glbox';
  var dl = found.map(function(f){
    return '<dt></dt><dd data-m="' + (f[2] ? '1' : '') + '"></dd>';
  }).join('');
  box.innerHTML = '<summary>📘 이 쪽에 나온 어려운 말 ' + found.length + '개</summary><dl>' + dl + '</dl>';
  if (wasOpen) box.open = true;
  var dts = box.querySelectorAll('dt'), dds = box.querySelectorAll('dd');
  found.forEach(function(f, j){
    dts[j].textContent = f[0];
    dds[j].textContent = f[1];
    if (f[2]){ var i2 = document.createElement('i'); i2.textContent = f[2]; dds[j].appendChild(i2); }
  });
  /* 펼치는 순간 다시 센다. 쪽이 제 내용을 다시 그려 주석 하나가 사라져도,
     읽는 사람이 보는 목록은 늘 본문과 같다. */
  box.addEventListener('toggle', function(){
    if (!box.open) return;
    var now = {}, list = [];
    document.querySelectorAll('.plainterm').forEach(function(b){
      var t = b.textContent;
      if (now[t] || !DEF[t]) return;
      now[t] = 1; list.push([t, DEF[t][0], DEF[t][1]]);
    });
    list.sort(function(a, b2){ return a[0].localeCompare(b2[0], 'ko'); });
    if (list.length === box.querySelectorAll('dt').length) return;
    box.querySelector('summary').textContent = '📘 이 쪽에 나온 어려운 말 ' + list.length + '개';
    var dl2 = box.querySelector('dl');
    dl2.innerHTML = '';
    list.forEach(function(f){
      var dt = document.createElement('dt'); dt.textContent = f[0];
      var dd = document.createElement('dd'); dd.textContent = f[1];
      if (f[2]){ var i3 = document.createElement('i'); i3.textContent = f[2]; dd.appendChild(i3); }
      dl2.appendChild(dt); dl2.appendChild(dd);
    });
    lastSig = list.map(function(f){ return f[0]; }).sort().join('|');
  });
  var cr = document.querySelector('.site-credit');
  if (cr) cr.parentNode.insertBefore(box, cr); else document.body.appendChild(box);
  }
})();
</script>""".replace('__TERMS__', data)


_TERMS_RE = re.compile(r'\s*<script>\s*/\* 쉬운 말 풀이.*?</script>', re.S)


def inject_terms(path):
    """쉬운 말 풀이 장치를 붙인다. 이미 있으면 새것으로 갈아 끼운다."""
    s = open(path, encoding='utf-8').read()
    before = s
    s = _TERMS_RE.sub('', s)
    js = terms_js()
    if '</body>' in s:
        s = s.replace('</body>', js + '\n</body>', 1)
    else:
        s = s.rstrip() + '\n' + js + '\n'
    if s == before:
        return False
    open(path, 'w', encoding='utf-8').write(s)
    return True


def printfoot_html():
    return ('<div class="printonly printfoot">'
            '⚠️ 질병관리청 공식 누리집이 아닌 공공자료 정리·분석 프로젝트의 참고용 정리물이다. '
            '잠정통계가 포함돼 있으며, 법적·의학적 판단은 최신 공식 원문과 전문가 확인을 거쳐야 한다. '
            '연도를 이어 비교하기 전에 단절점을 확인할 것.'
            '</div>')


def inject(path, depth):
    """depth: 포털 루트까지의 깊이(0=index, 1=하위 폴더)"""
    s = open(path, encoding='utf-8').read()
    if 'id="btnPrint"' in s:
        # 이미 넣은 쪽이라도 머리글·꼬리말 문구는 매번 최신으로 바꾼다.
        # 예전에는 여기서 그냥 돌아서서, 문구를 고쳐도 새로 만든 쪽에만 반영됐다.
        m = re.search(r'<title>(.*?)</title>', s, re.S)
        title = re.sub(r'\s+', ' ', m.group(1)).strip() if m else '감염병 자료 아카이브'
        s2 = re.sub(r'<div class="printonly printhead" id="printhead">.*?</div>',
                    printhead_html(title), s, count=1, flags=re.S)
        s2 = re.sub(r'<div class="printonly printfoot">.*?</div>',
                    printfoot_html(), s2, count=1, flags=re.S)
        # 나중에 생긴 공용 스타일은 이미 주입된 쪽에도 넣어 준다.
        # 이 갈래로 돌아서는 바람에 크레딧 스타일이 스물두 쪽에 안 붙던 일이 있었다.
        # 자리가 중요하다. 메뉴 CSS는 매번 걷어내고 다시 넣는데, 그 걷어내는 범위가
        # 메뉴 주석부터 </style> 까지다. 그 뒤에 두면 다음 조립 때 같이 지워진다.
        for css, probe in ((CREDIT_CSS, '.site-credit{'), (TERMS_CSS, '.glpop{'),
                           (SUMMARY_CSS, '.plainsum{')):
            if probe in s2:
                continue
            mark = '\n/* ── 공통 메뉴'
            if mark in s2:
                s2 = s2.replace(mark, css + mark, 1)
            elif '</style>' in s2:
                s2 = s2.replace('</style>', css + '</style>', 1)
        if s2 != s:
            open(path, 'w', encoding='utf-8').write(s2)
            return True
        return False
    m = re.search(r'<title>(.*?)</title>', s, re.S)
    title = re.sub(r'\s+', ' ', m.group(1)).strip() if m else '감염병 자료 아카이브'
    up = '../' * depth
    # 1) 인쇄 CSS — 첫 </style> 앞에 넣어 그 파일의 색 토큰을 덮어쓴다
    marker = '/* ── 인쇄'
    if '</style>' in s:
        s = s.replace('</style>', PRINT_CSS + CREDIT_CSS + TERMS_CSS + SUMMARY_CSS + '\n</style>', 1)
    else:
        s = s.replace('</head>', f'<style>{PRINT_CSS}{CREDIT_CSS}{TERMS_CSS}{SUMMARY_CSS}</style>\n</head>', 1)
    # 2) 인쇄용 머리글.
    #    포털에는 <body>가 있는 완전한 문서와 <title>로 시작하는 조각 파일이 섞여 있다.
    #    조각 파일에 맨 앞으로 넣으면 <title>보다 앞서므로, 스타일 블록 뒤에 넣는다.
    head_html = printhead_html(title)
    body = re.search(r'<body[^>]*>', s)
    if body:
        s = s[:body.end()] + '\n' + head_html + s[body.end():]
    else:
        idx = s.find('</style>', s.find(marker)) if marker in s else -1
        if idx >= 0:
            cut = idx + len('</style>')
            s = s[:cut] + '\n' + head_html + s[cut:]
        else:
            s = head_html + s
    # 3) 도구 막대 + 인쇄용 꼬리말 + JS — 본문 끝
    tail = tools_html(up + 'data/') + printfoot_html() + PRINT_JS
    if '</body>' in s:
        s = s.replace('</body>', tail + '\n</body>', 1)
    else:
        s += tail
    open(path, 'w', encoding='utf-8').write(s)
    return True


# 검색 결과에 뜨는 한 줄. 쪽마다 제 템플릿에 적는 것이 맞지만 열한 쪽이 비어 있었고,
# 템플릿이 제각각이라 한 곳에서 채운다. 템플릿에 이미 있으면 건드리지 않는다.
DESCRIPTIONS = {
    'field': '감염병 한 종의 급수·신고기한·격리·잠복기와 펴야 할 지침을 한 화면에 모았습니다. 역학조사 현장에서 바로 확인합니다.',
    'checker': '두 연도의 감염병 통계를 그대로 비교해도 되는지 먼저 확인합니다. 감시체계·분류가 바뀐 지점을 짚어 줍니다.',
    'guides': '질병관리청 관리지침과 서식을 감염병별·연도별로 찾습니다. 원문 게시물로 바로 연결합니다.',
    'vaccine': '국가예방접종 접종률과 감염병별 집단면역 문턱을 함께 봅니다. 접종률의 기준이 해마다 달라진 점도 밝힙니다.',
    'lab': '병원체 검출 감시 결과를 주 단위로 봅니다. 신고 건수와는 다른 축의 자료입니다.',
    'pathogen': '법정감염병 91종을 병원체의 모양과 분류로 다시 세어 봅니다.',
    'whitepaper': '질병관리청 백서를 연도별로 모아 원문으로 연결합니다. 그해를 정리한 공식 기록입니다.',
    'hall': '1954년부터 지금까지 해마다 무엇이 달라졌는지 전시물로 걸어 두었습니다. 연도별 시간축으로 훑어봅니다.',
    'flu': '인플루엔자 감시 100년을 절기별 유행, 아형 구성, WHO 백신 구성 권고로 나누어 봅니다.',
    'cross': '신고 건수와 병원체 검출 수를 맞대어 봅니다. 숫자 하나만으로는 알 수 없는 것을 확인합니다.',
    'policy': '검역관리지역에서 나라를 넣고 빼면 무엇이 달라지는지 실험합니다. 위험을 판정하지 않고 구조만 보여 줍니다.',
}


def ensure_description(path, current):
    """<meta name="description">이 없으면 이 쪽에 맞는 한 줄을 넣는다."""
    desc = DESCRIPTIONS.get(current)
    if not desc:
        return False
    s = open(path, encoding='utf-8').read()
    if re.search(r'<meta[^>]+name=["\']description', s, re.I):
        return False
    tag = f'<meta name="description" content="{desc}">'
    if '</title>' in s:
        s = s.replace('</title>', '</title>\n' + tag, 1)
    else:
        s = tag + '\n' + s
    open(path, 'w', encoding='utf-8').write(s)
    return True


def ensure_head(path):
    """문자셋·언어 선언이 없는 쪽에 머리를 세운다.

    조각 파일로 시작한 쪽(허브·법령·인플루엔자)은 <title>부터 시작한다. GitHub Pages가
    응답 헤더로 utf-8을 붙여 주기 때문에 지금까지 드러나지 않았지만, 다른 호스팅이나
    파일로 열면 한글이 깨진다. 선언은 문서가 스스로 갖고 있어야 한다.
    """
    s = open(path, encoding='utf-8').read()
    # 탭 아이콘 — 없으면 브라우저가 /favicon.ico 를 찾다가 콘솔에 404를 남긴다.
    # 하위 경로 호스팅이라 외부 파일 대신 문서 안에 그려 넣는다.
    if 'rel="icon"' not in s:
        ico = ('<link rel="icon" href="data:image/svg+xml,'
               '%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 100 100%27%3E'
               '%3Ctext y=%27.9em%27 font-size=%2790%27%3E%F0%9F%A6%A0%3C/text%3E%3C/svg%3E">')
        if '</title>' in s:
            s = s.replace('</title>', '</title>\n' + ico, 1)
        else:
            s = ico + '\n' + s
        open(path, 'w', encoding='utf-8').write(s)
    if re.search(r'<meta[^>]+charset', s, re.I):
        return False
    head = ('<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n')
    open(path, 'w', encoding='utf-8').write(head + s)
    return True


def inject_all(portal_dir):
    n = 0
    for dirpath, _, files in os.walk(portal_dir):
        for f in files:
            if f != 'index.html':
                continue
            p = os.path.join(dirpath, f)
            depth = 0 if os.path.dirname(p) == portal_dir else 1
            current = '' if depth == 0 else os.path.basename(dirpath)
            did = ensure_head(p)
            did = ensure_description(p, current) or did
            did = inject(p, depth) or did
            did = inject_nav(p, depth, current) or did
            did = inject_summary(p, current) or did
            did = inject_terms(p) or did
            did = inject_credit(p) or did
            if did:
                n += 1
                print('  도구·메뉴 주입', os.path.relpath(p, os.path.dirname(portal_dir)))
    return n
