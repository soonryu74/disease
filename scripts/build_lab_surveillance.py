#!/usr/bin/env python3
"""PHWR 부록 파싱 결과 → 10_진단검사_감시/data/*.csv 시계열.

주간 건강과 질병(PHWR)「주요 감염병 통계」의 병원체감시(진단검사) 표를 주차별로 합친다.
같은 주가 여러 호에 실리면 **나중 호**를 채택한다(잠정치 → 갱신치).

입력: scripts/parse_phwr_supple.py 가 만든 JSON (여러 호)
출력: 10_진단검사_감시/data/ 아래 CSV 5종 + 수집원장 JSON
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '10_진단검사_감시', 'data')

RESP = ['총검출률', '아데노', '보카', '파라인플루엔자', 'RSV', '리노', '메타뉴모',
        '코로나', '인플루엔자', '코로나19']
DIARV = ['노로', '그룹A로타', '장내아데노', '아스트로', '사포', '합계']
DIARB = ['살모넬라', '병원성대장균', '세균성이질', '장염비브리오', '비브리오콜레라',
         '캄필로박터', '클로스트리듐퍼프린젠스', '황색포도알균', '바실루스세레우스', '합계']


def issue_key(r):
    return (r.get('volume') or 0, r.get('number') or 0)


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f'  {os.path.relpath(path, ROOT)}  {len(rows)}행')


def main(paths):
    recs = []
    for p in paths:
        d = json.load(open(p, encoding='utf-8'))
        recs.extend(d if isinstance(d, list) else [d])
    recs.sort(key=issue_key)          # 오래된 호 → 최신 호 (뒤가 덮어씀)
    print(f'입력 {len(recs)}개 호')

    # ── 호흡기바이러스 주간 검출률 ────────────────────────────────
    resp = {}
    for r in recs:
        for row in r.get('respiratory') or []:
            resp[(row['year'], row['week'])] = dict(row, _src=f"{r['volume']}-{r['number']}")
    write_csv(os.path.join(OUT, '호흡기바이러스_주간검출률.csv'),
              ['연도', '주차'] + RESP + ['출처호'],
              [[k[0], k[1]] + [v.get(c) for c in RESP] + [v['_src']]
               for k, v in sorted(resp.items())])

    # ── 급성설사 바이러스 ────────────────────────────────────────
    dv = {}
    for r in recs:
        for row in r.get('diarrhea_virus') or []:
            dv[(row['year'], row['week'])] = dict(row, _src=f"{r['volume']}-{r['number']}")
    hdr = ['연도', '주차', '검체수']
    for c in DIARV:
        hdr += [c + '_건수', c + '_검출률']
    write_csv(os.path.join(OUT, '급성설사바이러스_주간검출.csv'), hdr + ['출처호'],
              [[k[0], k[1], v.get('specimens')]
               + [v.get(c + s) for c in DIARV for s in ('_건수', '_검출률')] + [v['_src']]
               for k, v in sorted(dv.items())])

    # ── 급성설사 세균 ────────────────────────────────────────────
    db = {}
    for r in recs:
        for row in r.get('diarrhea_bacteria') or []:
            db[(row['year'], row['week'])] = dict(row, _src=f"{r['volume']}-{r['number']}")
    hdr = ['연도', '주차', '검체수']
    for c in DIARB:
        hdr += [c + '_건수', c + '_분리율']
    write_csv(os.path.join(OUT, '급성설사세균_주간분리.csv'), hdr + ['출처호'],
              [[k[0], k[1], v.get('specimens')]
               + [v.get(c + s) for c in DIARB for s in ('_건수', '_분리율')] + [v['_src']]
               for k, v in sorted(db.items())])

    # ── 인플루엔자 양성률·아형 (호마다 1주) ───────────────────────
    flu = {}
    for r in recs:
        f = r.get('influenza')
        if not f or 'week' not in f:
            continue
        y = int((f.get('as_of') or r.get('date') or '0000')[:4])
        flu[(y, f['week'])] = dict(f, _src=f"{r['volume']}-{r['number']}")
    write_csv(os.path.join(OUT, '인플루엔자_양성률.csv'),
              ['연도', '주차', '기준일', '양성률', 'A_H1N1pdm09', 'A_H3N2', 'B', '표본의료기관수', '출처호'],
              [[k[0], k[1], v.get('as_of'), v.get('positivity'), v.get('H1N1pdm09'),
                v.get('H3N2'), v.get('B'), v.get('sentinel_clinics'), v['_src']]
               for k, v in sorted(flu.items())])

    # ── 엔테로바이러스 ───────────────────────────────────────────
    ev = {}
    for r in recs:
        e = r.get('enterovirus')
        if not e or 'week' not in e:
            continue
        y = int((e.get('as_of') or r.get('date') or '0000')[:4])
        ev[(y, e['week'])] = dict(e, _src=f"{r['volume']}-{r['number']}")
    write_csv(os.path.join(OUT, '엔테로바이러스_주간검출.csv'),
              ['연도', '주차', '기준일', '검출률', '양성건수', '검체수',
               '무균성수막염', '수족구병_포진성구협염', '합병증동반수족구병', '기타', '출처호'],
              [[k[0], k[1], v.get('as_of'), v.get('positivity'), v.get('positive'),
                v.get('specimens'), v.get('무균성수막염'), v.get('수족구병'),
                v.get('합병증동반수족구병'), v.get('기타'), v['_src']]
               for k, v in sorted(ev.items())])

    # ── 수집 원장 ────────────────────────────────────────────────
    ledger = [{'권': r['volume'], '호': r['number'], '발행일': r['date'],
               '호흡기주차': len(r.get('respiratory') or []),
               '설사바이러스주차': len(r.get('diarrhea_virus') or []),
               '설사세균주차': len(r.get('diarrhea_bacteria') or []),
               '인플루엔자': bool(r.get('influenza')),
               '엔테로바이러스': bool(r.get('enterovirus'))} for r in recs]
    os.makedirs(OUT, exist_ok=True)
    json.dump({'수집호수': len(recs), '원장': ledger},
              open(os.path.join(OUT, '수집원장.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f"  {os.path.relpath(os.path.join(OUT, '수집원장.json'), ROOT)}")

    def span(d):
        if not d:
            return '없음'
        ks = sorted(d)
        out = []
        for y in sorted({k[0] for k in ks}):
            w = sorted(k[1] for k in ks if k[0] == y)
            miss = [x for x in range(min(w), max(w) + 1) if x not in w]
            out.append(f'{y}년 {min(w)}~{max(w)}주({len(w)}주)' + (f' 결손 {miss}' if miss else ''))
        return ' · '.join(out)

    print('\n주차 범위')
    for name, d in (('호흡기', resp), ('설사바이러스', dv), ('설사세균', db),
                    ('인플루엔자', flu), ('엔테로', ev)):
        print(f'  {name}: {span(d)}')


if __name__ == '__main__':
    main(sys.argv[1:])
