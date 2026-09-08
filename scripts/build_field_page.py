#!/usr/bin/env python3
"""현장 대응 카드 → portal/field/

역학조사 현장에서 한 화면에 있어야 하는 것을 모은다.
 - 지금 이 병의 급·신고기한·격리 (⑨ 연대기)
 - 펴야 할 지침 (⑭ 지침 색인)
 - 잠복기와 그 값이 국제 기준과 맞는지 (⑭ 국제기준 대조)
 - 역학조사서 서식·교재·매뉴얼 (⑭ 교육·매뉴얼)
"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D14 = os.path.join(ROOT, '14_역학조사_실무', 'data')
CHRON = os.path.join(ROOT, '09_감염병연대기', 'data', '연대기.json')
DOGAM = os.path.join(ROOT, '05_감염병_질병정보')
OUT = os.path.join(ROOT, 'portal', 'field', 'index.html')


def norm(s):
    return re.sub(r'[\s()·・\-]', '', s or '')


def dogam_fields():
    """도감에서 질병별 잠복기·감염경로·치료·예방을 뽑는다."""
    out = {}
    for f in sorted(os.listdir(DOGAM)):
        if not f.startswith('제') or not f.endswith('.md'):
            continue
        txt = open(os.path.join(DOGAM, f), encoding='utf-8').read()
        for block in re.split(r'\n#{2,3} ', txt):
            head = block.split('\n')[0].strip()
            head = re.sub(r'🆕|\s*\([^)]*\)\s*$', '', head).strip()
            if not head or len(head) > 40:
                continue
            rec = {}
            for key, pat in (('잠복기', r'\*\*잠복기\*\*\s*[:：]\s*([^\n]+)'),
                             ('감염경로', r'\*\*(?:감염경로|경로)\*\*\s*[:：]\s*([^\n]+)'),
                             ('치료', r'\*\*치료(?:/예방)?\*\*\s*[:：]\s*([^\n]+)'),
                             ('예방', r'\*\*예방\*\*\s*[:：]\s*([^\n]+)'),
                             ('신고', r'\*\*(?:급수/신고|신고)\*\*\s*[:：]\s*([^\n]+)')):
                m = re.search(pat, block)
                if m:
                    rec[key] = re.sub(r'\*\*|⚠️', '', m.group(1)).strip()
            if rec:
                out[norm(head)] = rec
    return out


def current_phase(dz):
    cur = None
    for p in dz['phases']:
        if (p.get('status') or '').startswith('제'):
            cur = p
    return cur or {}


def build():
    idx = json.load(open(os.path.join(D14, '감염병별_지침색인.json'), encoding='utf-8'))
    edu = json.load(open(os.path.join(D14, '교육_매뉴얼.json'), encoding='utf-8'))
    chron = json.load(open(CHRON, encoding='utf-8'))
    dog = dogam_fields()

    cross = {}
    for name in ('호흡기', '수인성매개체'):
        c = json.load(open(os.path.join(D14, f'국제기준_대조_{name}.json'), encoding='utf-8'))
        for x in c['diseases']:
            cross[norm(x['disease'])] = x
    conflicts = []
    for name in ('호흡기', '수인성매개체'):
        c = json.load(open(os.path.join(D14, f'국제기준_대조_{name}.json'), encoding='utf-8'))
        conflicts += c['agency_conflicts']

    phase_by = {norm(d['name']): current_phase(d) for d in chron['diseases']}

    cards = []
    for e in idx['index']:
        k = norm(e['disease'])
        ph = phase_by.get(k, {})
        dg = dog.get(k, {})
        # 도감 이름이 조금 다를 수 있으니 부분일치로 한 번 더
        if not dg:
            for dk, dv in dog.items():
                if dk.startswith(k[:6]) or k.startswith(dk[:6]):
                    dg = dv
                    break
        xc = cross.get(k)
        if not xc:
            for ck, cv in cross.items():
                if ck.startswith(k[:5]) or k.startswith(ck[:5]):
                    xc = cv
                    break
        cards.append({
            'disease': e['disease'], 'icon': e['icon'], 'grade': e['grade'],
            'surv': ph.get('surv'), 'report': ph.get('report'), 'iso': ph.get('iso'),
            'incub': dg.get('잠복기'), 'route': dg.get('감염경로'),
            'tx': dg.get('치료'), 'prev': dg.get('예방'),
            'guides': e['direct'][:4], 'guides_total': e['direct_total'],
            'group_guides': e['group'][:3], 'primary': e.get('primary'),
            'cross': ({'verdict': xc['verdict'], 'why': xc['why'],
                       'impact': xc['field_impact'],
                       'intl': xc['international']} if xc else None),
        })

    data = {'cards': cards, 'edu': edu, 'meta': idx['meta'],
            'conflicts': conflicts,
            'counts': {
                'diseases': len(cards),
                'guidelines': idx['meta']['stats']['guidelines'],
                'crosschecked': sum(1 for c in cards if c['cross']),
                'narrower': sum(1 for c in cards if c['cross'] and c['cross']['verdict'] == 'narrower'),
                'forms': edu['forms']['total'],
            }}

    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'field.template.html'),
                encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__DATA__', js))
    print(f"→ portal/field/index.html  {os.path.getsize(OUT):,}B")
    print(f"  카드 {len(cards)} · 국제대조 {data['counts']['crosschecked']} · "
          f"잠복기 표기 {sum(1 for c in cards if c['incub'])} · 지침연결 "
          f"{sum(1 for c in cards if c['guides'] or c['group_guides'])}")


if __name__ == '__main__':
    build()
