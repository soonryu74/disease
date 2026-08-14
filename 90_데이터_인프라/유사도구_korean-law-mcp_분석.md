# 유사·상위 도구 분석 — `korean-law-mcp` (실측 포함)

> <https://github.com/chrisryugj/korean-law-mcp> · npm `korean-law-mcp` · MIT · TypeScript
> 법제처 국가법령정보 **42개 API를 10개 MCP 도구로** 통합한 오픈소스 MCP 서버. 만든이: 류주임(공무원).
> **우리가 §90에서 직접 만든 법제처 API 스크립트를 대체·확장하는 성숙한 도구.**

---

## 1. ✅ 실측 검증 (이 세션에서 직접 호출)

공개 엔드포인트 `https://mcp.gomdori.app/law?oc=test` 에 **설치·본인 OC 없이** JSON-RPC로 호출 성공(서버 v4.10.0).

| 호출 | 결과 |
|---|---|
| `initialize` | ✅ 200, serverInfo `korean-law` v4.10.0 |
| `tools/list` | ✅ 10개 도구 스키마 반환 |
| `search_law("감염병예방법")` | ✅ MST `280445`·법령ID `001792` + **시행예정본 2건까지 자동 안내** |
| `get_law_text(mst=280445, jo="제79조의3")` | ✅ 조문 전문 반환 |
| `legal_analysis(verify_citations)` | ✅ 인용 검증 동작(정식 법령명 필요) |
| `legal_analysis(applicable_law, date=2015-05-01)` | ✅ **기준일 시행 버전(시행 2014.9.19, MST 152012) + "이후 37차례 개정" + 부칙·경과조치** 반환 |
| `get_law_text(과거 MST 152012/212045)` | ✗ NOT_FOUND — 과거 버전 '전문'은 이 경로로 조회 불가(추측 대신 거부 = 안전장치). 대안: `applicable_law`로 시점 메타·부칙 확인 |

**교차검증 결과**: `get_law_text`가 반환한 제79조의3 = *"1년 이하의 징역 또는 1천만원 이하의 벌금 … 입원 또는 격리 조치를 위반한 자"* →
우리가 [§01 조항별 분석](../01_감염병예방법_연혁/조항별_강화_약화_분석.md)에서 손으로 검증한 내용과 **제3자 도구로도 완전 일치**. ✅

---

## 2. 제공 도구 (10개, v4.4+ 통폐합)

| 도구 | 역할 |
|---|---|
| `search_law` | 법령·조례·행정규칙 검색 → lawId·MST (약칭 자동변환, 시행예정 병기) |
| `get_law_text` | 조문 전문 (`mst` 필수, `jo`로 특정 조문, `efYd`로 시점 지정) |
| `get_annexes` | 별표/서식 (HWPX/PDF/XLSX 자동 변환) |
| `search_decisions` / `get_decision_text` | 18개 도메인(판례·헌재·조세심판·공정위 등) |
| `legal_research` | 다단계 리서치(task 8종) |
| `legal_analysis` | **verify_citations**(환각검증)·**cite_check**(판례 생사)·**applicable_law**(행위시법)·**impact_map**(조문 영향그래프) |
| `ordinance_radar` | 조례 정비 레이더 |
| `discover_tools`/`execute_tool` | 전문 도구 프록시 |

## 3. 우리 프로젝트와의 매핑

| 우리가 수동으로 한 것(§90) | 이 MCP |
|---|---|
| `curl OC=test` 로 API 호출 | `search_law`/`get_law_text` (봇차단 우회·재시도·캐시 내장) |
| 현행 XML 받아 손으로 원문 검증 | `verify_citations` 자동 |
| `eflaw`로 연도별 버전 수집 | `applicable_law`(행위시법)·시점 지정 `efYd` |
| "OC 발급하면 lsHistory로 조문 연혁 가능"이라 남겨둠 | **이미 구현됨** (시점 조문 diff) |
| 별표 이미지 별도 | `get_annexes` 자동 변환 |

## 4. 사용법 요약

**A. 설치 없이 (공개 서버)** — claude.ai 커스텀 커넥터에 URL 등록:
```
https://mcp.gomdori.app/law?oc=<본인OC 또는 test>
```
**B. 로컬**: `npm install -g korean-law-mcp` → Claude Desktop/Cursor 설정
**C. 직접 호출(JSON-RPC)**: 위 §1 실측 예시 참고(초기화→tools/call)

## 5. 평가 · 주의

**장점**: 우리 자체 스크립트가 겪은 문제(JS 렌더링, 봇차단, lsHistory 미신청)를 이미 해결. 인용 검증·시점 비교·판례까지 커버. 공개 서버로 진입장벽 0.

**주의**:
- README의 star/fork 수치·수상 배지는 **GitHub 페이지에서 직접 확인 권장**(요약 오독 가능). 기능·도구·API 연동은 신뢰도 높음(실측으로 확인).
- 공개 서버는 rate limit(분당 120). 대량 작업은 본인 OC 권장.
- `verify_citations`는 **정식 법령명**("감염병의 예방 및 관리에 관한 법률")을 줘야 정확. 약칭만 주면 '확인필요'.
- 법적 효력 판단은 반드시 원문 확인(도구도 동일 경고).

## 6. 우리 프로젝트 활용 권고
1. **§90 인프라 보완**: 자체 스크립트(원천 재현용)는 유지 + **조문 연혁·인용 검증은 이 MCP로**.
2. **§01 조항별 분석 확대**: `applicable_law`/시점 조회로 강화·완화를 **전 조문·연도별**로 확장.
3. **④ 사업화**와 연계: 우리 감염병 지식베이스 + 이런 법령 MCP를 결합하면 "감염병 법·지침 통합 질의" 서비스의 백엔드로 유용.
