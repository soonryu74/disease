#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""본인 OC(인증키)로 법제처 API 사용 — 연혁 전용(lsHistory)·조문 변경이력까지.
사용법:
    export LAW_OC=본인OC          # 예: export LAW_OC=hong  (hong@korea.kr 이면 hong)
    python3 fetch_with_oc.py test        # OC 유효성 + 각 API 신청여부 점검
    python3 fetch_with_oc.py history 001792   # 감염병예방법 연혁목록(lsHistory)
    python3 fetch_with_oc.py jochange 001792  # 조문별 변경이력(강화/완화 조문 추적용)
OC 미설정 시 공개 테스트키 test 사용(law/eflaw만 가능, lsHistory는 미신청 에러).
"""
import os, sys, urllib.request, urllib.parse, ssl

OC = os.environ.get('LAW_OC', 'test')
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def call(kind, target, **params):
    base = f"https://www.law.go.kr/DRF/{'lawSearch' if kind=='search' else 'lawService'}.do"
    q = {'OC': OC, 'target': target, 'type': 'XML'}; q.update(params)
    url = base + '?' + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    body = urllib.request.urlopen(req, timeout=40, context=ctx).read().decode('utf-8', 'ignore')
    return url, body

def is_error(body):
    return ('미신청' in body) or ('<html' in body[:200].lower())

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'test'
    print(f"[OC = {OC}]  ({'본인 키' if OC!='test' else '공개 테스트키'})\n")
    if cmd == 'test':
        checks = [('현행법령 law', 'search', 'law', {'query': '감염병'}),
                  ('시행일법령 eflaw', 'search', 'eflaw', {'query': '감염병'}),
                  ('법령연혁 lsHistory', 'search', 'lsHistory', {'query': '감염병의 예방 및 관리에 관한 법률'})]
        for name, kind, tgt, p in checks:
            try:
                _, body = call(kind, tgt, **p)
                print(f"  {'❌ 미신청/오류' if is_error(body) else '✅ 사용가능'}  {name}")
            except Exception as e:
                print(f"  ⚠️ 요청실패  {name}: {e}")
        print("\n❌가 있으면 open.law.go.kr → [OPEN API 신청]에서 해당 항목 체크 후 승인 필요.")
    elif cmd == 'history':
        lid = sys.argv[2] if len(sys.argv) > 2 else '001792'
        url, body = call('search', 'lsHistory', query='감염병의 예방 및 관리에 관한 법률')
        print("요청:", url, "\n"); print(body[:4000])
    elif cmd == 'jochange':
        lid = sys.argv[2] if len(sys.argv) > 2 else '001792'
        # 조문별 변경 이력: target=lsJoHstInf (본인 OC 신청 필요)
        url, body = call('search', 'lsJoHstInf', ID=lid)
        print("요청:", url, "\n"); print(body[:4000])

if __name__ == '__main__':
    main()
