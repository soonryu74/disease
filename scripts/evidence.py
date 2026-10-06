#!/usr/bin/env python3
"""근거 원장 문지기.

이 사이트가 틀렸던 이유는 하나였다 — **구조에서 사실을 추론**했다.
법정 급수에서 격리방식을, 최대 잠복기에서 감시 종료일을, 문서 제목에서 대표 지침을
뽑아냈다. 구조는 사실의 대용품이 아니다.

그래서 규칙을 뒤집는다. 임상·행정 조치 기준은 근거 원장
(14_역학조사_실무/data/근거원장.json)에 출처가 적힌 것만 값으로 나간다.
없으면 값을 만들지 않고 '공식 근거 확인 필요'와 원문 접근 경로를 내보낸다.

빌더는 이 모듈을 거치지 않고 임상 값을 쓰면 안 된다. 그것이 재발 방지다.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, '14_역학조사_실무', 'data', '근거원장.json')

with open(LEDGER, encoding='utf-8') as f:
    L = json.load(f)

DOCS = L['문서']


def norm(s):
    """이름 맞추기 — 괄호·공백·가운뎃점을 털어 낸다."""
    s = (s or '').strip()
    for a, b in (('·', ''), ('‧', ''), ('・', ''), (' ', ''), ('(', ''), (')', ''),
                 ('[', ''), (']', ''), ('-', ''), ('–', '')):
        s = s.replace(a, b)
    return s


def _index(section, key='질병'):
    out = {}
    for row in L[section]['항목']:
        out[norm(row[key])] = row
    return out


ISO = _index('격리_및_감염관리')
CONTACT = _index('접촉자_관리')
NEED = L['확인필요']


def doc(doc_id):
    """문서 한 건의 서지 정보. 날짜는 쓰임새가 달라 하나로 합치지 않는다."""
    d = DOCS.get(doc_id)
    if not d:
        return None
    return {
        'id': doc_id,
        'title': d['제목'],
        'printed': d.get('문서표기'),       # 문서 표지에 찍힌 판 — 게시연도와 다를 수 있다
        'posted': d.get('게시일'),
        'revised': d.get('최종수정일'),
        'effective': d.get('시행일'),        # 없으면 없는 것이다. 게시일로 메우지 않는다
        'office': d.get('담당부서'),
        'tel': d.get('연락처'),
        'tel_checked': d.get('연락처_확인일'),
        'url': d.get('게시글'),
        'file': d.get('첨부'),
        'collected': d.get('수집확인일'),
        'licence': d.get('이용조건'),
        'note': d.get('주'),
    }


def _cite(row):
    """주장 한 줄에 붙는 출처 꼬리표. 쪽수와 검토상태까지 함께 간다."""
    d = doc(row['출처']) or {}
    return {
        'doc': row['출처'],
        'title': d.get('title'),
        'printed': d.get('printed'),
        'posted': d.get('posted'),
        'revised': d.get('revised'),
        'effective': d.get('effective'),
        'page': row.get('쪽'),
        'review': row.get('검토상태'),
        'reviewed': row.get('검토일'),
        'url': d.get('url'),
        'file': d.get('file'),
    }


def _gap(what, disease, why=None):
    """값 대신 내보내는 '빈 자리'. 무엇이 없는지와 어디서 확인하는지를 같이 준다."""
    return {
        'ok': False,
        'status': '공식 근거 확인 필요',
        'what': what,
        'disease': disease,
        'why': why or NEED.get(what + '_주') or NEED.get(what),
        'where': [
            {'label': '질병관리청 감염병 지침 게시판',
             'url': 'https://www.kdca.go.kr/bbs/kdca/55/artclList.do'},
            # 상대 경로로 둔다. 절대 경로는 로컬에서 깨지고 배포 경로가 바뀌면 또 깨진다.
            {'label': '이 사이트의 지침 서가에서 해당 질환 찾기', 'url': '../guides/'},
        ],
    }


def isolation(disease):
    """격리·감염관리. 급수에서 추론하지 않는다 — 원장에 있으면 값, 없으면 빈 자리."""
    row = ISO.get(norm(disease))
    if not row:
        return _gap('격리_및_감염관리', disease,
                    '법정 급수는 신고 기한의 근거이지 감염관리 방법의 근거가 아니다. '
                    '이 질환의 격리방식은 질환별 공식 지침에서 확인해야 한다.')
    return {
        'ok': True,
        'disease': disease,
        'case': row.get('사례분류'),
        'admit': row.get('입원치료'),
        'isolation': row.get('격리'),
        'precautions': row.get('감염관리'),
        'negpress_required': row.get('음압격리_필수'),
        'bed': row.get('병상배정'),
        'lab': row.get('검사기관'),
        'transport': row.get('검체운송'),
        'contacts': row.get('접촉자조사'),
        'release': row.get('격리해제'),           # ⑦ 해제·종결
        'infectious': row.get('전염기'),          # 전염 가능 기간 — 격리기간과 다른 값이다
        'incub_doc': row.get('잠복기_지침값'),
        'specimen': row.get('검체'),
        'spec_site': row.get('검체채취_장소'),
        'spec_test': row.get('검사항목'),
        'lab_req': row.get('검사의뢰'),
        'report': row.get('보고'),
        'move': row.get('환자이송'),
        'note': row.get('주'),
        'cite': _cite(row),
    }


def contact(disease):
    """접촉자 감시. '최대 잠복기' 한 줄로 뭉뚱그리지 않는다."""
    row = CONTACT.get(norm(disease))
    if not row:
        return _gap('접촉자_관리', disease,
                    '접촉자 감시 기간은 최대 잠복기 하나로 정해지지 않는다. '
                    '기산점, 예방요법 투여 여부, 면역 상태, 시설 환경에 따라 달라진다. '
                    '이 질환의 기준은 질환별 공식 지침의 접촉자 관리 절에서 확인해야 한다.')
    return {
        'ok': True,
        'disease': disease,
        'start': row.get('기산점'),
        'period': row.get('기본_감시기간'),
        'extend': row.get('연장_조건'),
        'example': row.get('계산_예시'),
        'pep': row.get('예방요법') or [],
        'exclusion': row.get('업무_등교_제한') or [],
        'immunity': row.get('면역_판정'),
        'jurisdiction': row.get('관할'),
        'school': row.get('학교_접촉자_접종력_확인'),
        'who': row.get('분류'),                   # 누구를 접촉자로 보는가
        'suspect': row.get('의사환자_단계'),       # 의사환자 단계와 확진 단계는 조치가 다르다
        'confirmed': row.get('확진환자_단계') or [],
        'common': row.get('공통_관리'),
        'method': row.get('감시_방법'),
        'scope': row.get('범위설정'),
        'flight': row.get('항공기_조사'),
        'form': row.get('서식'),
        'passive_note': row.get('수동감시_안내'),
        'entry': row.get('결과입력'),
        'note': row.get('주'),
        'cite': _cite(row),
    }


def common_notes(section='격리_및_감염관리'):
    return [dict(x, cite=_cite(x)) for x in L[section].get('공통_주', [])]


def gaps():
    """원장이 스스로 밝히는 빈 자리 목록. 보고와 점검에 쓴다."""
    return NEED


def stats():
    return {
        'docs': len(DOCS),
        'isolation': len(ISO),
        'contact': len(CONTACT),
        'isolation_gap': len(NEED.get('격리_및_감염관리', [])),
    }


if __name__ == '__main__':
    s = stats()
    print(f"문서 {s['docs']}건 · 격리 근거 {s['isolation']}종 "
          f"(확인 필요 {s['isolation_gap']}종) · 접촉자 근거 {s['contact']}종")
    for d in ('보툴리눔독소증', '탄저', '에볼라바이러스병'):
        r = isolation(d)
        print(f"  {d}: " + (f"{r['isolation']}  [{r['cite']['review']}]" if r['ok']
                            else r['status']))
    r = contact('홍역')
    print(f"  홍역 접촉자: {r['period']} / 연장 {('있음' if r['extend'] else '없음')}")
