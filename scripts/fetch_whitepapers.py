#!/usr/bin/env python3
"""③ 백서 목록 — 질병관리청백서 게시판(kdca.go.kr/kdca/2873)에서 발간 이력을 뽑는다.

이 쪽의 핵심은 **화면에 안 보이는 항목**이다. 2004~2011·2014~2015년 백서는
HTML 소스에 `<!--li ... li-->` 로 주석 처리돼 있고 내려받기 주소가 비어 있다.
표지 이미지는 살아 있으므로 '발간은 됐는데 원문이 사라졌다'가 확인된다.
그래서 화면에 보이는 것만 긁으면 안 되고, 주석 안까지 읽어야 한다.

산출: 03_백서_정리/data/백서_목록.json
"""
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '03_백서_정리', 'data', '백서_목록.json')
COVERS = os.path.join(ROOT, '03_백서_정리', 'data', 'covers')
URL = 'https://www.kdca.go.kr/kdca/2873/subview.do'
BASE = 'https://www.kdca.go.kr'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

LI = re.compile(
    r'<(?P<c>!--)?li[^>]*>\s*<img[^>]*src="(?P<img>[^"]+)"[^>]*>\s*'
    r'<p>(?P<label>.*?)</p>\s*<a href="(?P<href>[^"]*)"[^>]*>\s*다운로드\s*</a>',
    re.S)


def get(url, tries=5):
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '-m', '90', '-A', UA, url], capture_output=True, text=True)
        if p.stdout and len(p.stdout) > 20000:
            return p.stdout
        time.sleep(2 + i * 3)
    return ''


def head(url, tries=3):
    """표지 이미지가 서버에 남아 있는지 — '발간은 됐다'의 근거"""
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '-o', '/dev/null', '-m', '40', '-A', UA,
                            '-w', '%{http_code} %{size_download}', '-r', '0-0', url],
                           capture_output=True, text=True)
        parts = p.stdout.split()
        if parts and parts[0].isdigit() and parts[0] != '000':
            return int(parts[0])
        time.sleep(1 + i * 2)
    return 0


def save_cover(url):
    """표지를 저장소로 받아 둔다.
    유실된 9판은 표지가 유일하게 남은 흔적이다. 남의 서버에 걸어 두면 그것마저 사라질 수 있다."""
    name = re.sub(r'[^\w.~()-]', '_', url.rsplit('/', 1)[-1])
    path = os.path.join(COVERS, name)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return name
    os.makedirs(COVERS, exist_ok=True)
    for i in range(6):
        p = subprocess.run(['curl', '-sS', '-m', '60', '-A', UA, '-o', path, url])
        if p.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 1000:
            return name
        time.sleep(2 + i * 2)
    if os.path.exists(path):
        os.remove(path)
    return ''


def main():
    h = get(URL)
    if not h:
        sys.exit('게시판을 못 받았다. 기존 파일을 지우지 않는다.')
    # 주석 블록은 `<!--li ... li-->` 로 여러 항목을 통째로 감싼다. 여는 태그에만 `!--` 가
    # 붙으므로 항목마다 보고 판단하면 첫 줄만 숨김으로 잡힌다. 구간을 먼저 잡아 둔다.
    dark = [(m.start(), m.end()) for m in re.finditer(r'<!--li.*?li-->', h, re.S)]

    items = []
    for m in LI.finditer(h):
        label = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m.group('label'))).strip()
        href = m.group('href').strip()
        hidden = any(a <= m.start() < b for a, b in dark)
        items.append({
            'label': label,
            'cover': BASE + m.group('img'),
            'file': BASE + href if href.rstrip('/') != '/sites/kdca/download' and href else '',
            'hidden': hidden,
        })
    if len(items) < 15:
        sys.exit(f'항목이 너무 적다({len(items)}건). 게시판 구조가 바뀌었다.')

    # 표지가 살아 있는지 실측 — 숨겨진 판이 '실재했다'는 증거
    for it in items:
        if it['hidden']:
            it['cover_status'] = head(it['cover'])
        it['cover_file'] = save_cover(it['cover'])

    # 2022년 영문판이 2023년 파일을 가리키는 링크 오류 — 자동으로 다시 확인한다
    dup = {}
    for it in items:
        if it['file']:
            dup.setdefault(it['file'], []).append(it['label'])
    mislinked = {f: ls for f, ls in dup.items() if len(ls) > 1}

    data = {
        'as_of': time.strftime('%Y-%m-%d'),
        'source': URL,
        'items': items,
        'hidden': sum(1 for i in items if i['hidden']),
        'downloadable': sum(1 for i in items if i['file']),
        'mislinked': mislinked,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    got = sum(1 for i in items if i['cover_file'])
    print(f'백서 게시판 {len(items)}항목 — 내려받기 {data["downloadable"]} · 숨겨진(주석) {data["hidden"]} · 표지 확보 {got}')
    for it in items:
        if it['hidden']:
            print(f'  숨김 {it["label"]}  표지 HTTP {it.get("cover_status")}  파일 {it["file"] or "없음"}')
    for f, ls in mislinked.items():
        print(f'  ⚠️ 링크 중복 — {" / ".join(ls)} 가 같은 파일을 가리킨다: {os.path.basename(f)}')
    print(f'  → {os.path.relpath(OUT, ROOT)}')


if __name__ == '__main__':
    main()
