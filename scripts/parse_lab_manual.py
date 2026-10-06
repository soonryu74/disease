#!/usr/bin/env python3
"""「법정감염병 진단검사 통합지침」 PDF → 14_역학조사_실무/data/검체.json

왜 만들었나
  현장카드의 ④ 검사·검체 칸이 오래 비어 있었다. 질환별 대응지침은 검사기관과
  검체 운송 주체까지만 적고, 검체 종류·채취 시점·용기·보관 조건은 이 통합지침으로 넘긴다.
  그 지침이 바로 '적정 검체와 검체 채취시기 및 용기, 세부 검사법 등의 정보를 제공'한다고
  목적에 적어 두었다(본문 2쪽).

무엇을 뽑나
  질환마다 — 검체 종류, 검사법별 채취 시기·용기·채취량·보관 온도, 참고사항, 원문 쪽번호.
  표를 글자 위치가 아니라 줄 구조로 읽는다. 열 이름이 고정돼 있어 그 편이 튼튼하다.

무엇을 뽑지 않나
  판정 기준과 세부 검사법의 실험 절차. 현장 담당자가 검체를 채취해 의뢰하는 데
  필요한 것만 싣는다. 실험실 절차는 원문을 봐야 한다.

쓰는 법
  python3 scripts/parse_lab_manual.py <PDF 경로>
  PDF: https://www.kdca.go.kr/bbs/kdca/55/308526/download.do
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '14_역학조사_실무', 'data', '검체.json')

SRC = {
    '제목': '법정감염병 진단검사 통합지침(제5판)',
    '게시일': '2026-07-23',
    '게시글': 'https://www.kdca.go.kr/bbs/kdca/55/311901/artclView.do',
    '첨부': 'https://www.kdca.go.kr/bbs/kdca/55/308526/download.do',
    '수집확인일': '2026-10-06',
    '목적': '법정감염병의 신고를 위한 확인진단을 수행하는 데 있어 적정 검체와 검체 채취시기 및 용기, 세부 검사법 등의 정보를 제공',
}

# [제1급-14] 같은 꼬리표가 질환의 시작을 알린다
TAG = re.compile(r'\[제([1-4])급-([0-9]+(?:-[가-힣])?)\]')
PAGE = re.compile(r'(?:www\.kdca\.go\.kr\s*_\s*(\d{3})|(\d{3})\s*_\s*질병관리청)')
# 표의 열 이름 — 이 줄이 나오면 그 아래가 채취 조건 표다
TABLE_HEAD = re.compile(r'검사법\s*검체\s*채취\s*시기\s*채취\s*용기\s*채취량\s*채취\s*후\s*보관')
TEMP = re.compile(r'(-?\s?\d+\s*(?:~\s*-?\s?\d+\s*)?℃|실온|냉장|냉동)')


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def printed_page(text):
    m = PAGE.search(text)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def split_diseases(pages):
    """꼬리표를 경계로 질환 덩어리를 가른다. 머리글에도 꼬리표가 나오므로
    '꼬리표 바로 뒤에 한글 병명이 오는' 쪽만 시작으로 친다."""
    blocks, cur = [], None
    for n, raw in pages:
        t = raw or ''
        m = TAG.search(t)
        starts = False
        name = None
        if m:
            after = clean(t[m.end():m.end() + 120])
            # 쪽머리글은 꼬리표 앞뒤 어디에나 끼어든다. 자리를 가리지 않고 걷어 낸다.
            # (이걸 '맨 앞에만' 걷어 내게 짰더니 '카바페넴내성장내세균목(CRE) 감염증 112 _ 질병관리청'
            #  처럼 쪽번호가 이름 뒤에 붙은 쪽을 통째로 놓쳤다.)
            after = re.sub(r'\d{3}\s*_\s*질병관리청', ' ', after)
            after = re.sub(r'www\.kdca\.go\.kr\s*_\s*\d{3}', ' ', after)
            after = clean(after)
            mm = re.match(r'([가-힣][가-힣A-Za-z0-9()·\-\s]{1,39}?)'
                          r'\s*(?:[A-Z][a-z]|Ⅰ\s*\.|$)', after)
            if mm and re.search(r'[가-힣]{2}', mm.group(1)):
                starts, name = True, clean(mm.group(1))
        if starts:
            if cur:
                blocks.append(cur)
            cur = {'grade': '제' + m.group(1) + '급', 'no': m.group(2), 'name': name,
                   'pdf_from': n, 'printed': printed_page(t), 'text': [t]}
        elif cur:
            cur['text'].append(t)
            cur['pdf_to'] = n
    if cur:
        blocks.append(cur)
    return blocks


def parse_specimen(text):
    """'2. 검체 : ...' 한 줄."""
    m = re.search(r'2\.\s*검체\s*[:：]\s*(.{3,400}?)(?=\n\s*검사법|\n\s*3\.\s|\Z)', text, re.S)
    return clean(m.group(1)) if m else None


def parse_table(text):
    """채취 조건 표 — 열 이름 줄 다음부터 '3. 세부검사법' 전까지.

    한 행은 '검체명 채취시기 용기 채취량 [보관온도]' 가 한 줄로 붙어 나온다.
    가장 믿을 만한 닻은 **용기 이름**이다(수송배지·무균용기 등 몇 가지뿐).
    그래서 용기를 먼저 찾아 줄을 둘로 가르고, 왼쪽에서 검체명과 채취시기를,
    오른쪽에서 채취량과 보관온도를 뗀다. 끝에서부터 벗기면 서로 엉킨다.
    """
    m = TABLE_HEAD.search(text)
    if not m:
        return []
    seg = text[m.end():]
    seg = re.split(r'\n\s*3\.\s*세부검사법|\n\s*4\.\s*판정|Ⅲ\.\s*참고사항', seg)[0]

    CONTAINER = re.compile(r'(수송배지|무균용기|멸균용기|전용용기|배양용기|혈청분리관|'
                           r'EDTA\s*튜브|헤파린\s*튜브|멸균\s*면봉|용기)')
    METHOD = re.compile(r'^(유전자검출검사|항원검출검사|항체검출검사|분리배양검사|배양검사|'
                        r'현미경검사|독소검출검사|[가-힣]{2,10}검사)$')
    rows, method, temp = [], None, None
    for ln in seg.split('\n'):
        ln = clean(ln)
        if not ln or len(ln) < 4:
            continue
        if METHOD.match(ln):          # 검사법 이름만 있는 줄 — 아래 행들이 이 검사법에 속한다
            method = ln
            continue
        tm = TEMP.search(ln)
        if tm and len(ln) <= 14:      # 온도만 떨어진 줄 — 아래 행들에 공통으로 적용된다
            temp = clean(tm.group(0))
            continue
        row_temp = None
        if tm:
            row_temp = clean(tm.group(0))
            ln = clean(ln[:tm.start()] + ' ' + ln[tm.end():])

        cm = CONTAINER.search(ln)
        if not cm:
            continue                  # 용기가 없으면 표의 행이 아니다(각주·이어진 글)
        left, right = clean(ln[:cm.start()]), clean(ln[cm.end():])
        container = clean(cm.group(1))

        am = re.match(r'^(\d+(?:\.\d+)?\s*(?:mL|ml|g|매)(?:\s*이상)?|\d+\s*개의?\s*\S+|'
                      r'적당량|전량)', right)
        amount = clean(am.group(1)) if am else (clean(right) or None)

        wm = re.search(r'(증상\s*발현.*|발진\s*발생.*|발병.*|급성기.*|회복기.*|의심\s*시.*|'
                       r'가능한\s*한.*|진단\s*시.*|채취\s*가능.*|확진\s*시.*)$', left)
        when = clean(wm.group(1)) if wm else None
        name = clean(left[:wm.start()]) if wm else clean(left)
        name = re.sub(r'\d+$', '', name).strip()     # 각주 번호 꼬리를 뗀다
        if not name or len(name) > 30:
            continue
        rows.append({'검사법': method, '검체': name, '채취시기': when,
                     '용기': container, '채취량': amount,
                     '보관온도': row_temp or temp})
    return rows


def parse_notes(text):
    m = re.search(r'Ⅲ\.\s*참고사항(.{0,900}?)(?=\[제[1-4]급|\Z)', text, re.S)
    if not m:
        return []
    out = []
    for ln in m.group(1).split('❖'):
        ln = clean(ln)
        if len(ln) > 8:
            out.append(ln[:400])
    return out[:4]


def build(pdf_path):
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    from fetch_guideline_pdf import pages as read_pages
    pages = read_pages(pdf_path)
    blocks = split_diseases(pages)

    out = {}
    for b in blocks:
        text = '\n'.join(b['text'])
        rows = parse_table(text)
        spec = parse_specimen(text)
        if not spec and not rows:
            continue
        # 표에서 읽은 행을 스스로 검산한다.
        # 같은 쪽의 '2. 검체 :' 줄이 그 질환의 검체를 이미 글로 적어 두었으므로,
        # 행의 검체명이 그 목록에 들어 있지 않으면 잘못 읽은 것으로 보고 버린다.
        # 표가 여러 줄로 접히거나 괄호 주석이 끼면 행이 어긋나는데, 그걸 그대로 싣느니
        # 버리고 '원문을 보라'고 적는 편이 낫다.
        declared = re.sub(r'[,·]', ' ', spec or '')
        good, dropped = [], 0
        for r in rows:
            nm = r['검체']
            if nm and 2 <= len(nm) <= 14 and re.fullmatch(r'[가-힣A-Za-z0-9()]+', nm) \
               and (nm in declared or any(nm in w or w in nm
                                          for w in declared.split() if len(w) > 1)):
                good.append(r)
            else:
                dropped += 1

        out[b['name']] = {
            'grade': b['grade'], 'no': b['no'],
            '검체': spec,
            '채취조건': good,
            '검산_버린행': dropped,
            '표_확인필요': dropped > 0,
            '참고사항': parse_notes(text),
            '쪽': (f"본문 {b['printed']}쪽 (PDF {b['pdf_from']}번째 장)"
                  if b['printed'] else f"PDF {b['pdf_from']}번째 장"),
        }

    data = {'schema': '검체/1', '출처': SRC, '검토상태': '원문 자동 추출 — 표본 대조',
            '주': ('표를 줄 구조로 읽어 낸 값이다. 아래 표본은 사람이 원문과 대조했다. '
                  '대조하지 않은 질환은 값이 원문과 다를 수 있으니 쪽번호로 원문을 확인할 것.'),
            '질환': out}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'→ {os.path.relpath(OUT, ROOT)}')
    ok = sum(1 for v in out.values() if v['채취조건'])
    clean_ = sum(1 for v in out.values() if v['채취조건'] and not v['표_확인필요'])
    print(f'  질환 {len(out)}종 · 검체 목록 {sum(1 for v in out.values() if v["검체"])}종')
    print(f'  채취조건 행이 남은 질환 {ok}종 (그 가운데 버린 행 없이 깨끗한 질환 {clean_}종)')
    print(f'  검산에서 버린 행 합계 {sum(v["검산_버린행"] for v in out.values())}개')
    return data


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    build(sys.argv[1])
