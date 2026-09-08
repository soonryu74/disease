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
import os
import re

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
NAV_ITEMS = [
    ('', '🏠', '허브'), ('dogam/', '📖', '도감'), ('pathogen/', '🧫', '병원체'),
    ('chronicle/', '📜', '연대기'), ('checker/', '🩺', '검사기'), ('field/', '🚑', '현장카드'),
    ('inflow/', '🌐', '유입지도'), ('cross/', '🧪', '교차검증'), ('lab/', '🔬', '진단검사'),
    ('quarantine/', '🛂', '검역'), ('policy/', '🎛', '정책실험'), ('daily/', '📡', '상황판'), ('flu/', '🦠', '인플루엔자'),
    ('law/', '⚖', '법령'), ('data/', '⬇', '자료실'),
]
NAV_CSS = """
/* ── 공통 메뉴 ─────────────────────────────────────────────────────── */
nav:not(.gnav){display:none !important}
.gnav{position:sticky;top:0;z-index:70;background:color-mix(in srgb,var(--ground,#F5F7F6) 90%,transparent);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line,#DCE4E1);
  font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',system-ui,sans-serif;letter-spacing:-.01em}
.gnav .gin{max-width:1100px;margin:0 auto;padding:9px 16px;display:flex;align-items:center;gap:2px;
  overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.gnav .gin::-webkit-scrollbar{display:none}
.gnav .gbrand{font-weight:800;font-size:13.5px;color:var(--ink,#16211D);white-space:nowrap;margin-right:10px;text-decoration:none;flex:none}
.gnav .gbrand i{color:var(--accent,#0E6E63);font-style:normal}
.gnav a.gi{font-size:12.5px;color:var(--muted,#5B6B65);padding:5px 8px;border-radius:8px;font-weight:600;
  white-space:nowrap;text-decoration:none;flex:none;line-height:1.4}
.gnav a.gi:hover{background:var(--surface-2,#EEF2F0);color:var(--ink,#16211D)}
.gnav a.gi.on{background:var(--accent,#0E6E63);color:#fff}
@media (min-width:1000px){.gnav .gin{flex-wrap:wrap;overflow:visible}}
"""


def nav_html(up, current):
    items = []
    for href, icon, label in NAV_ITEMS:
        on = ' on' if href.rstrip('/') == current else ''
        items.append(f'<a class="gi{on}" href="{up}{href or "./"}">{icon} {label}</a>')
    return (f'<nav class="gnav"><div class="gin">'
            f'<a class="gbrand" href="{up}./">🦠 감염병 자료 아카이브<i>.</i></a>'
            + ''.join(items) + '</div></nav>'
            # 좁은 화면에서 현재 쪽 항목이 보이도록 가로로 굴린다
            '<script>(function(){var a=document.querySelector(".gnav a.on");'
            'if(a){var p=a.parentNode;p.scrollLeft=a.offsetLeft-p.clientWidth/2+a.offsetWidth/2;}})();</script>')


def inject_nav(path, depth, current):
    s = open(path, encoding='utf-8').read()
    # 이미 있으면 걷어내고 다시 넣는다 — 메뉴 항목이 바뀌면 모든 쪽이 같이 바뀌어야 한다
    s = re.sub(r'\n?<nav class="gnav">.*?</nav>(?:<script>.*?</script>)?', '', s, flags=re.S)
    s = s.replace(NAV_CSS + '\n', '')
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
    open(path, 'w', encoding='utf-8').write(s)
    return True


def tools_html(data_href='data/', home='./'):
    return (f'<div class="pagetools">'
            f'<button id="btnPrint" type="button" title="이 페이지를 인쇄하거나 PDF로 저장">🖨 인쇄</button>'
            f'<a href="{data_href}" title="이 사이트가 쓰는 원자료 내려받기">⬇ 자료받기</a>'
            f'</div>')


def printhead_html(title):
    return ('<div class="printonly printhead" id="printhead">'
            f'<b>{title}</b> — 감염병 자료 아카이브 · 제작 지움웍스(jieumworks.com)<br>'
            '<span class="purl"></span> · <span class="pdate"></span> · '
            '원자료: 질병관리청 · 법제처'
            '</div>')


def printfoot_html():
    return ('<div class="printonly printfoot">'
            '⚠️ 참고용 정리물이다. 잠정통계가 포함돼 있으며, 법적·의학적 판단은 원문과 '
            '전문가 확인을 거쳐야 한다. 연도를 이어 비교하기 전에 단절점을 확인할 것.'
            '</div>')


def inject(path, depth):
    """depth: 포털 루트까지의 깊이(0=index, 1=하위 폴더)"""
    s = open(path, encoding='utf-8').read()
    if 'id="btnPrint"' in s:
        return False
    m = re.search(r'<title>(.*?)</title>', s, re.S)
    title = re.sub(r'\s+', ' ', m.group(1)).strip() if m else '감염병 자료 아카이브'
    up = '../' * depth
    # 1) 인쇄 CSS — 첫 </style> 앞에 넣어 그 파일의 색 토큰을 덮어쓴다
    marker = '/* ── 인쇄'
    if '</style>' in s:
        s = s.replace('</style>', PRINT_CSS + '\n</style>', 1)
    else:
        s = s.replace('</head>', f'<style>{PRINT_CSS}</style>\n</head>', 1)
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


def inject_all(portal_dir):
    n = 0
    for dirpath, _, files in os.walk(portal_dir):
        for f in files:
            if f != 'index.html':
                continue
            p = os.path.join(dirpath, f)
            depth = 0 if os.path.dirname(p) == portal_dir else 1
            current = '' if depth == 0 else os.path.basename(dirpath)
            did = inject(p, depth)
            did = inject_nav(p, depth, current) or did
            if did:
                n += 1
                print('  도구·메뉴 주입', os.path.relpath(p, os.path.dirname(portal_dir)))
    return n
