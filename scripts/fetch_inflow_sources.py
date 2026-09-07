#!/usr/bin/env python3
"""⑮ 해외유입 지도 — 원자료 수집·정규화

세 갈래를 받아 15_해외유입_지도/data/ 에 떨군다.

 1. 법무부 국적(지역)별 외국인 입국자 (월별)
    https://www.data.go.kr/data/15099989/fileData.do  · 이용허락범위 제한 없음
    ※ '국적' 기준이다. 어디서 탔는지가 아니라 여권이 어디 것인지다.

 2. 국토교통부 지역·국가별 항공통계 — 도착 여객 (항공정보포털 조회 API)
    https://www.airportal.go.kr/stats/transport/chartDetail4.do
    ※ '노선' 기준이다. 직항이 있는 나라만 잡히고 환승은 출발지가 아니라 경유지로 잡힌다.

 3. Natural Earth 110m admin-0 (public domain) → 투영·간략화한 세계지도
    https://github.com/nvkelso/natural-earth-vector

수집 자체가 실패해도 조용히 넘어가지 않는다. 실패하면 그 자리에서 멈춘다.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '15_해외유입_지도', 'data')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

MOJ_PAGE = 'https://www.data.go.kr/data/15099989/fileData.do'
MOJ_FILE = 'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={fid}&fileDetailSn=1'
AIR_PAGE = 'https://www.airportal.go.kr/stats/transport/chartDetail4.do'
AIR_API = 'https://www.airportal.go.kr/stats/transport/getDetailedAirTransportStats4.do'
NE_URL = ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/'
          'master/geojson/ne_110m_admin_0_countries.geojson')

# 조회 기간: 12개월이 원격 API의 상한이라 창을 나눠 받는다.
WINDOWS = [('202401', '202412'), ('202501', '202512'), ('202601', '202607')]


def curl(url, *, post=None, referer=None, jar=None, tries=6):
    """망이 자주 끊긴다. 지수 백오프로 다시 건다."""
    for i in range(1, tries + 1):
        cmd = ['curl', '-sS', '-L', '-A', UA]
        if referer:
            cmd += ['-e', referer]
        if jar:
            cmd += ['-b', jar, '-c', jar]
        if post is not None:
            cmd += ['-X', 'POST', '-H', 'Content-Type: application/json;charset=UTF-8',
                    '-d', post]
        cmd.append(url)
        p = subprocess.run(cmd, capture_output=True)
        if p.returncode == 0 and p.stdout:
            return p.stdout
        time.sleep(i * 2)
    sys.exit(f'수집 실패 (재시도 {tries}회): {url}')


def fetch_moj(jar):
    """공공데이터포털은 첨부파일 ID가 갱신될 때마다 바뀐다. 상세 쪽에서 긁어온다."""
    import re
    page = curl(MOJ_PAGE, jar=jar).decode('utf-8', 'replace')
    m = re.search(r'atchFileId=([A-Za-z0-9_]+)', page)
    if not m:
        sys.exit('법무부 첨부파일 ID를 상세 쪽에서 찾지 못했다.')
    raw = curl(MOJ_FILE.format(fid=m.group(1)), referer=MOJ_PAGE, jar=jar)
    text = raw.decode('cp949', 'replace')
    if '국적' not in text.split('\n', 1)[0]:
        sys.exit(f'법무부 파일 머리글이 예상과 다르다: {text.splitlines()[0][:80]}')
    path = os.path.join(OUT, '법무부_국적별_입국자.csv')
    open(path, 'w', encoding='utf-8', newline='').write(text)
    n = text.count('\n') - 1
    print(f'  법무부 국적별 입국자 {n:,}행 → {os.path.relpath(path, ROOT)}')
    return n


def fetch_air(jar):
    """도착 여객을 전체·환승 두 갈래로 받는다. 둘의 차가 실제로 들어온 사람에 가깝다."""
    import csv
    curl(AIR_PAGE, jar=jar)  # 세션 쿠키
    rows = {}
    for kind, pass_gubun in (('전체', 'total'), ('환승', '3')):
        for start, end in WINDOWS:
            body = json.dumps({'last_yearmonth': start, 'this_yearmonth': end,
                               'sn_gubun': '99', 'pass_gubun': pass_gubun,
                               'arvl_type': 'A', 'carge_gubun': 'total',
                               'pyn_gubun': 'Y'})
            res = json.loads(curl(AIR_API, post=body, referer=AIR_PAGE, jar=jar))
            for r in res.get('content') or []:
                name = (r.get('nation_name') or '').strip()
                if not name:
                    continue  # '전체 합계' 줄
                key = (start[:4], name)
                rec = rows.setdefault(key, {'연도': start[:4], '지역': r['area_name'],
                                            '국가': name, '도착편수': 0,
                                            '도착여객_전체': 0, '도착여객_환승': 0})
                if kind == '전체':
                    rec['도착편수'] = int(r.get('flight_cnt') or 0)
                rec[f'도착여객_{kind}'] = int(r.get('pass') or 0)
    path = os.path.join(OUT, '국토부_국가별_도착여객.csv')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['연도', '지역', '국가', '도착편수',
                               '도착여객_전체', '도착여객_환승'])
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])
    print(f'  국토부 국가별 도착여객 {len(rows):,}행 → {os.path.relpath(path, ROOT)}'
          f'  (연도 {", ".join(s[:4] for s, _ in WINDOWS)})')
    return len(rows)


def fetch_map():
    raw = curl(NE_URL)
    path = os.path.join(OUT, 'raw_ne_110m.geojson')
    open(path, 'wb').write(raw)
    print(f'  Natural Earth 110m {len(raw):,}B → {os.path.relpath(path, ROOT)}')
    return len(raw)


def main():
    os.makedirs(OUT, exist_ok=True)
    jar = os.path.join(OUT, '.cookies')
    print('원자료 수집')
    try:
        fetch_moj(jar)
        fetch_air(jar)
        fetch_map()
    finally:
        if os.path.exists(jar):
            os.remove(jar)
    print('  다음: python3 scripts/build_worldmap.py')


if __name__ == '__main__':
    main()
