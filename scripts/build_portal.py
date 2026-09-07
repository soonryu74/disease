#!/usr/bin/env python3
"""포털 번들 조립 — 빌드된 연대기·검사기 페이지를 portal/에 자체 포함 형태로 복사한다.

claude.ai 아티팩트 링크를 포털 내부 상대경로로 바꾸고, 완전한 HTML 문서로 감싼다.
실행 전 09_감염병연대기/build_chronicle.py, 08_비교가능성_검사기 빌드가 끝나 있어야 한다.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARTIFACT_TO_REL = {
    'https://claude.ai/code/artifact/bcbf2999-af6b-45a0-9f20-4d2504ddeb50': '../checker/',
    'https://claude.ai/code/artifact/b92f4396-92b2-4f70-b33c-112849e425e9': '../',
    'https://claude.ai/code/artifact/b0fb4b51-3197-4438-883e-b91caafd4595': '../flu/',
    'https://claude.ai/code/artifact/00d13129-712e-4ab8-b781-7da1b1ae9b7c': '../chronicle/',
}

# 포털 번들에만 추가하는 내비 링크(원본 페이지는 아티팩트로도 배포되므로 건드리지 않는다)
NAV_EXTRA = ('<a href="../dogam/">📖 도감</a>'
             '<a href="../lab/">🔬 진단검사</a>'
             '<a href="../quarantine/">🛂 검역</a>')


def wrap(src_path, out_path):
    s = open(os.path.join(ROOT, src_path), encoding='utf-8').read()
    for url, rel in ARTIFACT_TO_REL.items():
        s = s.replace(url, rel)
    if '</div></nav>' in s and '../quarantine/' not in s:
        s = s.replace('</div></nav>', NAV_EXTRA + '</div></nav>', 1)
    s = ('<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
         + s.replace('<title>', '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>', 1))
    s = s.replace('</style>', '</style>\n</head>\n<body>', 1) + '\n</body>\n</html>'
    out = os.path.join(ROOT, out_path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(s)
    print('portal <-', src_path, f'({os.path.getsize(out):,}B)')

def check_no_root_abs():
    bad = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'portal')):
        for f in files:
            if not f.endswith('.html'):
                continue
            s = open(os.path.join(dirpath, f), encoding='utf-8').read()
            for m in re.findall(r'(?:href|src)="(/[^"]*)"', s):
                bad.append((os.path.relpath(os.path.join(dirpath, f), ROOT), m))
    if bad:
        print('❌ 루트절대 경로 발견(하위 경로 호스팅에서 깨짐):')
        for f, m in bad:
            print('  ', f, m)
        sys.exit(1)
    print('✅ 루트절대 경로 없음 — 하위 경로 호스팅 안전')

if __name__ == '__main__':
    wrap('09_감염병연대기/연대기.html', 'portal/chronicle/index.html')
    wrap('08_비교가능성_검사기/단절점_검사기.html', 'portal/checker/index.html')
    check_no_root_abs()
