#!/usr/bin/env python3
"""연대기 전시관 조립 — 전시물 원장을 3차원 전시실로 옮긴다.

CSS 3D 변형으로 방을 세운다. 캔버스로 그리지 않는 이유는 하나다 —
전시물의 글자와 백서 표지가 그대로 살아 있어야 하고, 액자가 눌리는 단추여야 하기 때문이다.
캔버스에 그리면 예쁘지만 읽을 수도, 누를 수도, 검색할 수도 없다.

산출: portal/hall/index.html
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '09_감염병연대기', 'data', '전시물.json')
TPL = os.path.join(ROOT, 'scripts', 'templates', 'hall.template.html')
OUT = os.path.join(ROOT, 'portal', 'hall', 'index.html')


def build():
    d = json.load(open(SRC, encoding='utf-8'))
    # 전시실에 필요한 것만 싣는다 — 걸지 않은 전시물까지 보내면 자료가 두 배가 된다
    slim = {
        'as_of': d['as_of'], 'span': d['span'], 'total': d['total'],
        'themes': d['themes'], 'note': d['note'],
        'years': [{'y': y['y'], 'n': y['n'], 'rest': y['rest'],
                   'top': [{k: e[k] for k in ('date', 'theme', 'tag', 'title', 'body',
                                              'link', 'art', 'rank', 'why', 'see')
                            if e.get(k) not in (None, '', [])}
                           for e in y['top']]}
                  for y in d['years']],
    }
    js = json.dumps(slim, ensure_ascii=False, separators=(',', ':'))
    html = open(TPL, encoding='utf-8').read().replace('__DATA__', js)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)
    art = sum(1 for y in slim['years'] for e in y['top'] if e.get('art'))
    print(f"전시관 — 전시실 {len(slim['years'])}개 · 걸린 전시물 "
          f"{sum(len(y['top']) for y in slim['years'])}점(표지 그림 {art}점)")
    print(f'  → {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,}B)')


if __name__ == '__main__':
    build()
