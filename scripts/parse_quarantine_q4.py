#!/usr/bin/env python3
"""2026년 4분기 중점검역관리지역·검역관리지역 원문 PDF → 11_검역관리지역/data/2026Q4_지정내역.json

왜 따로 만들었나
  이 저장소는 2026.7.1.(3분기) 매트릭스를 쓰면서 9.7. 개정분을 '현행'이라 적고 있었다.
  그 사이 10.1. 시행 4분기 지정이 나왔다. '분기별 지정'이라는 말만 믿으면 늦는다.

무엇을 싣고 무엇을 싣지 않나
  - 중점검역관리지역: 국가 목록과 국가×감염병 표를 원문에서 뽑고, 지역별 국가 수와
    감염병별 국가 수를 공표치와 대조한다. 대조에 실패하면 파일을 쓰지 않고 멈춘다.
  - 검역관리지역(177개국): 지역별 국가 목록만 뽑는다. 국가×감염병 표는 쪽을 넘나드는
    넓은 표라 위치 기반 복원이 미덥지 않다. 그래서 '검증 대기'로 두고 원문 경로만 싣는다.
    확인하지 못한 것을 확인한 것처럼 적지 않는다.

쓰는 법
  python3 scripts/parse_quarantine_q4.py <내려받은 PDF 경로>
  PDF: https://www.kdca.go.kr/bbs/kdca/50/309847/download.do
"""
import json
import os
import re
import sys

import pypdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '11_검역관리지역', 'data', '2026Q4_지정내역.json')

SRC = {
    '제목': '2026년 4분기 중점검역관리지역 및 검역관리지역 안내',
    '게시일': '2026-09-18',
    '최종수정일': '2026-09-22',
    '시행일': '2026-10-01',
    '담당부서': '질병관리청 검역정책과',
    '연락처': '043-719-9211',
    '게시글': ('https://www.kdca.go.kr/kdca/2769/subview.do?enc='
             'Zm5jdDF8QEB8JTJGYmJzJTJGa2RjYSUyRjUwJTJGMzEyNjgzJTJGYXJ0Y2xWaWV3LmRvJTNG'),
    '첨부': 'https://www.kdca.go.kr/bbs/kdca/50/309847/download.do',
    '근거': '검역법 제5조(검역관리지역등의 지정)·제2조·제12조의2',
    '과태료': '1천만원 이하 과태료(검역법)',
    '이용조건': '공공누리 자유이용',
}

# 공표치 — 이 숫자와 맞지 않으면 파싱이 틀린 것이다.
EXPECT_PRI = {'아시아': 5, '중동': 13, '아프리카': 12, '미주': 2}
EXPECT_PRI_TOTAL = 32
EXPECT_GEN = {'아시아·중동': 42, '아프리카': 53, '미주·오세아니아': 63, '유럽': 19}
EXPECT_GEN_TOTAL = 177
EXPECT_PRI_DZ = {'페스트': 4, '동물인플루엔자인체감염증': 5, '중동호흡기증후군': 13,
                 '니파바이러스감염증': 2, '에볼라바이러스병': 11}


def tidy(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'\(([^)]*)\)', lambda m: '(' + m.group(1).replace(' ', '') + ')', s)


def split_countries(seg):
    """쉼표로 자르되 괄호 안의 쉼표(중국 성 이름 등)는 지킨다."""
    prot = re.sub(r'\(([^)]*)\)', lambda x: '(' + x.group(1).replace(',', '\x00') + ')', tidy(seg))
    return [n.strip().replace('\x00', ',') for n in prot.split(',') if n.strip()]


def pick(text, labels):
    """지역 이름표 사이의 덩어리를 가른다. PDF 가 글자 사이에 공백을 끼워 넣어도 되게."""
    pat = '|'.join(re.escape(x) for x in labels)
    out = {}
    for lab, key in labels.items():
        m = re.search(re.escape(lab) + r'(.*?)(?=' + pat + r'|대상 국가\(지역\)별|$)', text, re.S)
        if m:
            out[key] = split_countries(m.group(1))
    return out


def parse_priority(text):
    labels = {'아시아(5개)': '아시아', '중동(13개)': '중동',
              '아 프 리 카(12개)': '아프리카', '미주(2개)': '미주'}
    head = text.split('대상 국가(지역)별')[0]
    got = pick(head, labels)
    bad = {k: (len(got.get(k, [])), v) for k, v in EXPECT_PRI.items() if len(got.get(k, [])) != v}
    if bad:
        raise SystemExit(f'중점 지역별 국가 수가 공표치와 다르다 (뽑은 수, 공표 수): {bad}')
    total = sum(len(v) for v in got.values())
    if total != EXPECT_PRI_TOTAL:
        raise SystemExit(f'중점 합계 {total} ≠ 공표 {EXPECT_PRI_TOTAL}')
    return got


def parse_priority_matrix(text):
    """국가×감염병 — ● 가 어느 열인지는 줄 안에서의 순서로 푼다.
    중점 표는 열이 다섯뿐이고 국가마다 한 줄이라 이 방법이 통한다."""
    cols = ['페스트', '동물인플루엔자인체감염증', '중동호흡기증후군',
            '니파바이러스감염증', '에볼라바이러스병']
    body = text.split('대상 국가(지역)별')[-1]
    rows, cur = {}, None
    for raw in body.split('\n'):
        ln = raw.strip()
        m = re.match(r'^(\d+)\s+([^\d●]+?)\s*(●.*)?$', ln)
        if m and m.group(2).strip():
            cur = tidy(m.group(2))
            rows.setdefault(cur, [])
            if m.group(3):
                rows[cur].append(m.group(3))
        elif cur and '●' in ln:
            rows[cur].append(ln)
    return rows, cols


def parse_general(text):
    labels = {'아시아･중동': '아시아·중동', '아프리카': '아프리카',
              '미주･오세아니아': '미주·오세아니아', '유럽': '유럽'}
    head = text.split('대상 국가(지역)별')[0]
    out = {}
    for lab, key in labels.items():
        m = re.search(re.escape(lab) + r'\s*\((\d+)개\)(.*?)(?=아시아･중동|아프리카\s*\(|미주･오세아니아|유럽\s*\(|대상 국가|$)',
                      head, re.S)
        if m:
            out[key] = split_countries(m.group(2))
    bad = {k: (len(out.get(k, [])), v) for k, v in EXPECT_GEN.items() if len(out.get(k, [])) != v}
    if bad:
        raise SystemExit(f'검역관리지역 지역별 국가 수가 공표치와 다르다: {bad}')
    return out


def build(pdf_path):
    r = pypdf.PdfReader(pdf_path)
    t_pri = r.pages[1].extract_text() or ''
    t_gen = r.pages[2].extract_text() or ''

    pri = parse_priority(t_pri)
    gen = parse_general(t_gen)
    mat, cols = parse_priority_matrix(t_pri)

    data = {
        '기준': '2026년 4분기(2026.10.1. 시행)',
        '시행일': SRC['시행일'],
        '출처': SRC,
        '중점검역관리지역': {
            '감염병': list(EXPECT_PRI_DZ),
            '국가수': EXPECT_PRI_TOTAL,
            '지역별': pri,
            '감염병별_국가수_공표': EXPECT_PRI_DZ,
            '국가별_감염병_원문줄': mat,
            '검토상태': '원문대조',
            '검산': f'지역별 국가 수 {EXPECT_PRI} 및 합계 {EXPECT_PRI_TOTAL} 공표치와 일치',
        },
        '검역관리지역': {
            '국가수': EXPECT_GEN_TOTAL,
            '지역별': gen,
            '검토상태': '국가 목록만 원문대조',
            '국가별_감염병표': None,
            '미복원_사유': ('국가 177개 × 감염병 15개 표는 쪽을 넘나드는 넓은 표라 '
                        '위치 기반 복원의 정확도를 보증할 수 없다. 확인하지 못한 것을 '
                        '확인한 것처럼 싣지 않는다. 국가별 감염병은 원문 PDF를 확인할 것.'),
            '검산': f'지역별 국가 수 {EXPECT_GEN} 및 합계 {EXPECT_GEN_TOTAL} 공표치와 일치',
        },
        '수집확인일': '2026-10-05',
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'→ {os.path.relpath(OUT, ROOT)}')
    print(f'  중점 {EXPECT_PRI_TOTAL}개국 {dict((k, len(v)) for k, v in pri.items())} · 원문대조')
    print(f'  검역 {EXPECT_GEN_TOTAL}개국 {dict((k, len(v)) for k, v in gen.items())} · 국가 목록만 대조')
    print(f'  국가×감염병 줄 {len(mat)}개 복원 (중점만)')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    build(sys.argv[1])
