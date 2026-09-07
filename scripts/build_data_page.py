#!/usr/bin/env python3
"""공개 데이터 자료실 — 저장소의 CSV·JSON을 portal/data/ 로 복사하고 목록 페이지를 만든다.

GitHub Pages는 portal/ 만 배포하므로, 내려받게 하려면 파일이 그 안에 있어야 한다.
목록에는 행 수·크기·출처·주의사항을 함께 적는다. 파일만 받고 맥락을 모르면
이 저장소가 경고해 온 '단절점 모르고 비교하기'를 그대로 반복하게 된다.
"""
import csv
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'portal', 'data')
FILES = os.path.join(OUT, 'files')

# (그룹, 페이지경로, 그룹설명, [(원본경로, 설명, 주의)])
CATALOG = [
    ('⑮ 해외유입 지도', '../inflow/', '검역 지정 · 항공 도착 · 국적별 입국 · 유입 신고를 나라 하나로 묶은 표.', [
        ('15_해외유입_지도/data/국가별_유입_종합.csv',
         '219개국 — 직항 도착여객(환승 제외)·국적별 입국자·검역 지정 종수·유입 신고·백만 명당 건수.',
         '분모가 둘이다. 국적(여권)과 노선(항공권)은 서로 다른 사람을 센다. 신고 3건 미만의 비율은 순위로 쓰지 말 것.'),
        ('15_해외유입_지도/data/국토부_국가별_도착여객.csv',
         '국토교통부 지역·국가별 항공통계 — 2024·2025·2026(1~7월) 도착 여객기 전체·환승.',
         '직항 노선이 있는 나라만 있다. 경유 입국은 경유지 나라로 잡힌다.'),
        ('15_해외유입_지도/data/법무부_국적별_입국자.csv',
         '법무부 통계월보 — 2022-01~2026-07 월별·국적별 외국인 입국자 (공공데이터포털 15099989 원본).',
         '외국인만 있다. 우리 국민 귀국자는 없다.'),
    ]),
    ('⑬ 교차검증', '../cross/', '신고 축과 검출 축을 겹쳐 놓은 판정 결과.', [
        ('13_교차검증/data/교차검증.json',
         '대조쌍 7 · 이례 26 · 유입국 44 · 원문 발견 4건. 페이지가 그대로 쓰는 원본.',
         '판정은 이 저장소의 계산이며 질병관리청의 공식 해석이 아니다.'),
    ]),
    ('⑫ 신고 감시', '../lab/', '「주간 건강과 질병」 환자감시(신고) 표. 4주 간격 36개 주차.', [
        ('12_신고_감시/data/전수감시_주간신고.csv',
         '62종 × 36주 — 금주 신고수·연 누계·5년 주별 평균·예년대비배수.',
         "'열부분추출=Y'는 원문에서 5년평균 칸이 비어 열 수가 달랐던 행이다(매독·엠폭스). 앞 두 칸만 신뢰할 것."),
        ('12_신고_감시/data/해외유입_신고국가.csv',
         '유입 신고 193건 — 감염병 × 국가 × 신고수.',
         "2024년 43주 뎅기열의 '온두리스'는 원문 오기다(온두라스)."),
        ('12_신고_감시/data/표본감시_의사환자분율.csv',
         '인플루엔자 ILI·수족구·안과감염병 (외래 1,000명당) + 표본기관 수.', ''),
        ('12_신고_감시/data/연도별_확정신고수.csv', '감염병 × 연도 확정 통계.', ''),
        ('12_신고_감시/data/성매개감염병_기관당신고.csv', '5종 보고기관당 신고수.', ''),
        ('12_신고_감시/data/수인성식품매개_집단발생.csv', '주간 집단발생 건수·환자수.', ''),
        ('12_신고_감시/data/표기_원장.json',
         '원문 표기 흔들림과 통합 규칙.', 'CRE는 3년 사이 표기가 세 번 바뀌었다.'),
    ]),
    ('⑩ 진단검사 감시', '../lab/', '병원체감시(검출률) 표. 2023년 48주 ~ 2026년 35주.', [
        ('10_진단검사_감시/data/호흡기바이러스_주간검출률.csv',
         '총검출률 + 9종 주별 검출률(%). 139주.',
         '한 검체에서 둘 이상 검출될 수 있어 개별 병원체의 합은 총검출률과 다르다.'),
        ('10_진단검사_감시/data/급성설사세균_주간분리.csv',
         '검체 수 + 9종 건수·분리율. 138주.', ''),
        ('10_진단검사_감시/data/급성설사바이러스_주간검출.csv',
         '검체 수 + 5종 건수·검출률. 139주.', '5세 이하 아동 검체만 대상이다.'),
        ('10_진단검사_감시/data/인플루엔자_양성률.csv',
         '양성률 + 아형(H1N1pdm09·H3N2·B) + 표본의료기관 수.',
         '주간 시계열이 필요하면 호흡기바이러스 표의 인플루엔자 열을 쓰는 게 낫다.'),
        ('10_진단검사_감시/data/엔테로바이러스_주간검출.csv',
         '검출률 + 임상증후군별(무균성수막염·수족구병·합병증 동반·기타).', ''),
        ('10_진단검사_감시/data/수집원장.json', '어느 호에서 어떤 표를 몇 주치 얻었는지.', ''),
    ]),
    ('⑪ 검역관리지역', '../quarantine/', '검역법 제5조 지정. 원문 매트릭스를 복원하고 공표 국가 수와 대조 검산했다.', [
        ('11_검역관리지역/data/2026Q3_중점검역관리지역.csv',
         '25개국 × 5종 매트릭스 (2026.7.1. 기준).',
         '2026.9.7. 개정으로 현행은 31개국이다. 이 표는 대조 검산을 마친 시점의 것이다.'),
        ('11_검역관리지역/data/2026Q3_검역관리지역.csv',
         '173개국 × 15종 매트릭스 (2026.7.1. 기준).', ''),
        ('11_검역관리지역/data/지정이력.json',
         '2024년 상반기~2026년 3분기 시기별 요약 · 단절점 4건 · 세계 상황 매칭.',
         '분기 도중 개정이 잦다. 분기 시작일 자료만 보면 틀린다.'),
        ('11_검역관리지역/data/2026Q3_지정내역.json', '감염병별 국가 목록과 검산 결과.', ''),
    ]),
    ('⑨ 연대기 · ⑧ 검사기', '../chronicle/', '시점 인지형 국면과 비교 가능성 규칙.', [
        ('09_감염병연대기/data/연대기.json',
         '법정감염병 91종 × 국면(지위·감시·신고·격리·범위·분모) + 단절점 32건 + 오류 원장.',
         '⭐ 전 구간 원문 대조 12종 외 79종은 매핑표 기반 자동 생성이다.'),
        ('08_비교가능성_검사기/data/비교가능성_규칙.json',
         '81항목 비교 가능성 규칙 — 단절점·결측 구간·부분연도.', ''),
        ('05_감염병_질병정보/별칭사전.json',
         '옛 이름·별칭 사전(나병→한센병, 원숭이두창→엠폭스 등)과 시점별 유효 구간.', ''),
    ]),
    ('① 법령 · ② 지침 · ③ 백서', '../law/', '제도 축.', [
        ('01_감염병예방법_연혁/data/감염병예방법_연혁_전체.csv',
         '감염병예방법 시행 버전 연혁(1954~).', ''),
        ('01_감염병예방법_연혁/data/급수변동_이력.json',
         '급수·감시체계 변경 이력 16건.', ''),
        ('01_감염병예방법_연혁/data/감염병지정고시_연혁.json', '고시 지정 연혁.', ''),
        ('02_지침_정리/data/지침_전체목록_감염병포털.csv', '관리지침 358건 목록.', ''),
        ('03_백서_정리/data/전수감시_신고수_2016_2025.csv',
         '연보 기반 전수감시 신고수(2016~2025).', ''),
        ('03_백서_정리/data/표본감시_기관수_2001_2025.csv',
         '표본감시 참여기관 수(2001~2025) — 분모 변화 원장.',
         '기관 수가 바뀐 해는 앞뒤 비교가 불가능하다.'),
    ]),
]


def human(n):
    return f'{n/1024:.0f} KB' if n >= 1024 else f'{n} B'


def rows_of(path):
    if path.endswith('.csv'):
        with open(path, encoding='utf-8') as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)
    return None


def build():
    os.makedirs(FILES, exist_ok=True)
    groups = []
    total_files = total_bytes = 0
    for title, page, desc, items in CATALOG:
        entries = []
        for rel, note, caution in items:
            src = os.path.join(ROOT, rel)
            if not os.path.exists(src):
                print('  (없음, 건너뜀)', rel)
                continue
            name = os.path.basename(rel)
            dst = os.path.join(FILES, name)
            shutil.copy2(src, dst)
            size = os.path.getsize(dst)
            total_files += 1
            total_bytes += size
            entries.append({'file': name, 'note': note, 'caution': caution,
                            'size': human(size), 'rows': rows_of(dst),
                            'kind': 'CSV' if name.endswith('.csv') else 'JSON',
                            'repo': rel})
        if entries:
            groups.append({'title': title, 'page': page, 'desc': desc, 'items': entries})

    tmpl = open(os.path.join(ROOT, 'scripts', 'templates', 'data.template.html'),
                encoding='utf-8').read()
    js = json.dumps({'groups': groups, 'total_files': total_files,
                     'total_size': human(total_bytes)},
                    ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(
        tmpl.replace('__DATA__', js))
    print(f'→ portal/data/  파일 {total_files}개 · {human(total_bytes)}')


if __name__ == '__main__':
    build()
