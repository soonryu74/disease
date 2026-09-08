#!/usr/bin/env python3
"""병원체 형태 도감 → portal/pathogen/

05_감염병_질병정보/병원체_형태분류.json(손으로 쓴 형태 분류 91종)을 도감 91종과 대조해
빠진 것·이름이 다른 것이 없는지 확인한 뒤 템플릿에 넣는다. 3D는 브라우저가 그린다.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_dogam as bd  # noqa: E402

SRC = os.path.join(ROOT, '05_감염병_질병정보')
OUT = os.path.join(ROOT, 'portal', 'pathogen', 'index.html')


def dogam_names():
    names = {}
    for gnum, _, fname, _ in bd.GRADES:
        ds = bd.parse_file(os.path.join(SRC, fname))
        if gnum == '4':
            ds += bd.parse_resistant(os.path.join(SRC, fname))
        for d in ds:
            names[d['name']] = int(gnum)
    return names


def build():
    data = json.load(open(os.path.join(SRC, '병원체_형태분류.json'), encoding='utf-8'))
    names = dogam_names()
    mine = [d['name'] for d in data['diseases']]
    missing = sorted(set(names) - set(mine))
    extra = sorted(set(mine) - set(names))
    bad_grade = [d['name'] for d in data['diseases'] if names.get(d['name']) != d['grade']]
    classes = {c['id'] for c in data['classes']}
    bad_class = [d['name'] for d in data['diseases'] if d['class'] not in classes]
    if missing or extra or bad_grade or bad_class or len(mine) != len(set(mine)):
        raise SystemExit(f'형태분류가 도감과 어긋남 — 빠짐 {missing} · 남음 {extra} · 급수 불일치 {bad_grade} '
                         f'· 미정의 분류 {bad_class} · 중복 {len(mine) - len(set(mine))}')

    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'pathogen.template.html'),
                encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    used = {d['class'] for d in data['diseases']}
    sig = {}
    for d in data['diseases']:
        sig.setdefault(d['class'] + json.dumps(d.get('params', {}), sort_keys=True), []).append(d['name'])
    twins = [v for v in sig.values() if len(v) > 1]
    print(f"→ portal/pathogen/index.html  {os.path.getsize(OUT):,}B")
    print(f"  질병 {len(mine)} · 형태 {len(used)}/{len(classes)} · 형태로 구별 안 되는 묶음 {len(twins)}"
          f" ({sum(len(v) for v in twins)}종)")


if __name__ == '__main__':
    build()
