#!/usr/bin/env python3
"""⑯ 검역 정책 실험실 → portal/policy/

⑮가 결합해 둔 나라별 숫자(직항 도착여객·국적별 입국자·검역 지정·표본 유입 신고)를 그대로 가져와
브라우저에서 지정을 넣고 빼며 결과를 본다. 계산은 전부 클라이언트에서 한다.
여기서는 자료를 검사하고 템플릿에 넣기만 한다.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '15_해외유입_지도', 'data', '유입_종합.json')
OUT = os.path.join(ROOT, 'portal', 'policy', 'index.html')


def build():
    d = json.load(open(SRC, encoding='utf-8'))
    dz = d['quar_diseases']
    rows = [r for r in d['rows'] if r['iso'] != 'KOR']
    # 검사: 지정 목록의 병명이 15종 밖이면 멈춘다
    bad = {x for r in rows for x in r['q_general'] + r['q_priority']} - set(dz)
    if bad:
        raise SystemExit(f'검역감염병 15종 밖의 지정 병명: {bad}')
    pairs = sum(len(set(r['q_general']) | set(r['q_priority'])) for r in rows)
    rep = sum(x['n'] for r in rows for x in r['rep_quar'])
    slim = [{k: r[k] for k in ('iso', 'ko', 'region', 'air_direct', 'nat_entries',
                               'q_general', 'q_priority', 'rep_quar')} for r in rows]
    data = {'diseases': dz, 'rows': slim, 'meta': d['meta']}
    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'policy.template.html'),
                encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    print(f"→ portal/policy/index.html  {os.path.getsize(OUT):,}B")
    print(f"  나라 {len(rows)} · 검역감염병 {len(dz)} · 지정 쌍 {pairs} · 표본 검역감염병 유입 {rep}건")


if __name__ == '__main__':
    build()
