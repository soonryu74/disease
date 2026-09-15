#!/usr/bin/env python3
"""상황판 용어 사전 — 영어 원문의 핵심 낱말에 한글을 달기 위한 것.

번역기가 아니다. 원문 문장은 그대로 두고, 이 표에 있는 낱말만 찾아 '낱말(한글)'로 병기한다.
긴 표현을 먼저 맞춰야 'case'가 'confirmed case' 안에서 따로 잡히지 않는다 — 길이순 정렬은 쓰는 쪽에서 한다.

CDC 여행 알림 단계(LEVEL)와 WHO 위험도(RISK)는 값 자체를 한글로 옮긴다.
"""

GLOSSARY = {
    # 사건·규모
    'disease outbreak news': '질병 발생 뉴스',
    'outbreak': '발생(유행)', 'epidemic': '유행', 'pandemic': '대유행', 'cluster': '집단발생',
    'public health emergency of international concern': '국제공중보건위기상황',
    'pheic': '국제공중보건위기상황', 'international health regulations': '국제보건규칙',
    'ihr': '국제보건규칙', 'emergency committee': '긴급위원회', 'temporary recommendations': '임시 권고',
    'grade 3 emergency': '3등급 비상사태',
    # 사례 정의
    'laboratory-confirmed': '실험실 확진', 'confirmed cases': '확진 사례', 'confirmed case': '확진 사례',
    'probable cases': '추정 사례', 'probable case': '추정 사례', 'suspected cases': '의심 사례',
    'suspected case': '의심 사례', 'imported case': '유입 사례', 'imported cases': '유입 사례',
    'locally acquired': '지역 감염', 'autochthonous': '토착(지역 내 발생)', 'index case': '지표 환자',
    'cumulative': '누적', 'by date of notification': '신고일 기준', 'by date of onset': '증상 발현일 기준',
    'epidemiological week': '역학 주', 'notification': '신고',
    # 지표
    'case fatality ratio': '치명률', 'case fatality rate': '치명률', 'cfr': '치명률',
    'attack rate': '발병률', 'incidence': '발생률', 'prevalence': '유병률', 'mortality': '사망률',
    'morbidity': '이환', 'deaths': '사망', 'death': '사망', 'recovered': '회복', 'hospitalized': '입원',
    'hospitalizations': '입원', 'intensive care': '중환자 치료',
    'basic reproduction number': '기초재생산수', 'reproduction number': '재생산수',
    # 전파
    'incubation period': '잠복기', 'infectious period': '전염 기간', 'symptom onset': '증상 발현',
    'asymptomatic': '무증상', 'human-to-human transmission': '사람 간 전파',
    'person-to-person': '사람 간', 'transmission': '전파', 'zoonotic': '인수공통',
    'natural reservoir': '자연 숙주', 'reservoir': '병원소', 'vector-borne': '매개체 전파',
    'vector': '매개체', 'mosquito-borne': '모기매개', 'tick-borne': '진드기매개',
    'waterborne': '수인성', 'foodborne': '식품매개', 'airborne': '공기 전파', 'droplet': '비말',
    'bodily fluids': '체액', 'contaminated': '오염된', 'exposure': '노출', 'exposed': '노출된',
    'nosocomial': '병원 내 감염', 'health-care settings': '의료기관', 'health-care workers': '의료종사자',
    'healthcare workers': '의료종사자', 'unsafe burial': '안전하지 않은 장례',
    'safe and dignified burial': '안전한 장례',
    # 대응
    'contact tracing': '접촉자 추적', 'contacts': '접촉자', 'isolation': '격리', 'quarantine': '검역(격리)',
    'surveillance': '감시', 'active case finding': '적극적 사례 조사', 'case management': '환자 관리',
    'supportive care': '보존적 치료', 'infection prevention and control': '감염 예방·관리',
    'ipc': '감염 예방·관리', 'risk communication': '위험 소통', 'community engagement': '지역사회 참여',
    'vaccination campaign': '예방접종 캠페인', 'ring vaccination': '포위 접종', 'vaccination': '예방접종',
    'vaccine': '백신', 'vaccine coverage': '접종률', 'herd immunity': '집단면역',
    'antiviral': '항바이러스제', 'antibiotic': '항생제', 'antimicrobial resistance': '항생제 내성',
    'treatment centre': '치료센터', 'treatment center': '치료센터', 'points of entry': '입국 지점(검역소)',
    'cross-border': '국경 간', 'border': '국경', 'travel and trade': '여행·교역',
    'restriction of travel': '여행 제한', 'travel restrictions': '여행 제한', 'screening': '검사(선별)',
    'entry screening': '입국 검사', 'exit screening': '출국 검사',
    # 평가
    'risk assessment': '위험 평가', 'rapid risk assessment': '신속 위험 평가', 'very high': '매우 높음',
    'high': '높음', 'moderate': '보통', 'low': '낮음', 'national level': '국가 수준',
    'regional level': '지역 수준', 'global level': '세계 수준', 'advises against': '권고하지 않음',
    # 검사
    'polymerase chain reaction': '유전자 증폭 검사', 'pcr': '유전자 검사', 'rt-pcr': '유전자 검사',
    'sequencing': '염기서열 분석', 'genomic': '유전체', 'genome': '유전체', 'serotype': '혈청형',
    'genotype': '유전형', 'clade': '계통군', 'lineage': '계통', 'strain': '균주', 'variant': '변이',
    'sample': '검체', 'samples': '검체', 'specimen': '검체', 'tested positive': '양성 판정',
    'positive': '양성', 'negative': '음성', 'antibody': '항체', 'antigen': '항원',
    # 병 종류
    'viral haemorrhagic fever': '바이러스성 출혈열', 'viral hemorrhagic fever': '바이러스성 출혈열',
    'haemorrhagic': '출혈성', 'hemorrhagic': '출혈성', 'arbovirus': '절지동물매개 바이러스',
    'encephalitis': '뇌염', 'meningitis': '수막염', 'pneumonia': '폐렴', 'diarrhoea': '설사',
    'diarrhea': '설사', 'fever': '발열', 'rash': '발진', 'jaundice': '황달', 'paralysis': '마비',
    'acute flaccid paralysis': '급성 이완성 마비',
    # 기관·지역 단위
    'world health organization': '세계보건기구', 'who': '세계보건기구',
    'centers for disease control and prevention': '미국 질병통제예방센터', 'cdc': '미국 질병통제예방센터',
    'ministry of health': '보건부', 'health zone': '보건구역', 'health zones': '보건구역',
    'province': '주(도)', 'provinces': '주(도)', 'district': '구(군)', 'districts': '구(군)',
    'region': '지역', 'territory': '영토',
}

# CDC 여행 알림 단계 — 숫자 그대로 두면 뜻이 안 보인다
LEVEL = {
    1: ('Practice usual precautions', '평소 수준의 주의'),
    2: ('Practice enhanced precautions', '강화된 주의'),
    3: ('Reconsider nonessential travel', '불필요한 여행 재고'),
    4: ('Avoid all travel', '모든 여행 자제'),
}

RISK = {'very high': '매우 높음', 'high': '높음', 'moderate': '보통', 'low': '낮음'}

MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july',
                                       'august', 'september', 'october', 'november', 'december'], 1)}
