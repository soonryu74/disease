#!/usr/bin/env python3
"""질병관리청 지침 게시글 → 서지정보 + 첨부 PDF + 본문 텍스트

왜 필요한가
  근거 원장(14_역학조사_실무/data/근거원장.json)은 '원문에서 읽은 것'만 싣는다.
  그러려면 원문을 실제로 펴야 한다. 이 스크립트가 그 일을 맡는다.

무엇을 가져오나
  - 게시글에서 제목·작성일·최종수정일·담당부서·연락처 (원장의 날짜 칸이 이것들이다)
  - 첨부 파일 목록과 내려받기 주소
  - PDF 본문 텍스트 (쪽번호를 유지해서 원장에 '본문 N쪽 (PDF M번째 장)'을 적을 수 있게)

쓰는 법
  python3 scripts/fetch_guideline_pdf.py 312398            # 서지정보만
  python3 scripts/fetch_guideline_pdf.py 312398 --pdf      # 첫 PDF까지 내려받기
  python3 scripts/fetch_guideline_pdf.py 312398 --grep 격리 # 그 말이 나오는 쪽 찾기

주의
  게시판은 브라우저 User-Agent 가 아니면 빈 몸통을 돌려준다. 첨부 내려받기는
  게시글을 referer 로 주어야 한다. 둘 다 아래에 넣어 두었다.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, '.guideline_cache')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0 Safari/537.36')
BOARD = 'https://www.kdca.go.kr/bbs/kdca/{board}/{id}/artclView.do'


def curl(url, out=None, referer=None, timeout=120, tries=5):
    """게시판이 연결을 끊는 일이 잦다. 끊기면 간격을 늘려 가며 다시 걸어 본다."""
    import time
    cmd = ['curl', '-sS', '--max-time', str(timeout), '-A', UA, '-L']
    if referer:
        cmd += ['-e', referer]
    if out:
        cmd += ['-o', out]
    cmd.append(url)
    last = ''
    for i in range(tries):
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and (out is None or os.path.getsize(out) > 2000):
            return None if out else r.stdout.decode('utf-8', 'replace')
        last = r.stderr.decode()[:160] or f'내려받은 크기가 너무 작다'
        time.sleep(2 ** i)
    raise SystemExit(f'내려받기 실패 ({tries}번 시도): {last}')


def strip_tags(html):
    html = re.sub(r'<script[\s\S]*?</script>', ' ', html)
    html = re.sub(r'<style[\s\S]*?</style>', ' ', html)
    import html as H
    return re.sub(r'[ \t]+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ', html)))


def article(art_id, board=55):
    """게시글 서지정보와 첨부 목록."""
    url = BOARD.format(board=board, id=art_id)
    html = curl(url)
    txt = re.sub(r'\s+', ' ', strip_tags(html))

    def grab(label):
        m = re.search(re.escape(label) + r'\s*([^ ].{0,60}?)\s*(?=작성일|최종수정일|담당부서|연락처|$)', txt)
        return m.group(1).strip() if m else None

    files = []
    for m in re.finditer(r'href="(/bbs/kdca/\d+/(\d+)/download\.do)"', html):
        if m.group(1) not in [f['path'] for f in files]:
            files.append({'path': m.group(1), 'id': m.group(2),
                          'url': 'https://www.kdca.go.kr' + m.group(1)})
    # 첨부 이름은 본문 텍스트 순서와 대체로 같다
    names = re.findall(r'([^ ]{4,120}?\.(?:pdf|hwp|hwpx|zip|png|xlsx|docx))\s*다운받기', txt, re.I)
    for i, f in enumerate(files):
        f['name'] = names[i] if i < len(names) else ''

    title = None
    m = re.search(r'<h\d[^>]*>\s*([^<]{6,160}?)\s*</h\d>', html)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r'<title>\s*([^<]+?)\s*</title>', html)
        title = m.group(1).strip() if m else None

    return {'id': str(art_id), 'board': board, 'url': url, 'title': title,
            'posted': grab('작성일'), 'revised': grab('최종수정일'),
            'office': grab('담당부서'), 'tel': grab('연락처'), 'files': files}


def download(meta, which=0):
    os.makedirs(CACHE, exist_ok=True)
    f = meta['files'][which]
    out = os.path.join(CACHE, f"{meta['id']}_{f['id']}.pdf")
    if not os.path.exists(out) or os.path.getsize(out) < 10000:
        curl(f['url'], out=out, referer=meta['url'])
    return out


def pages(pdf_path):
    import pypdf
    r = pypdf.PdfReader(pdf_path)
    return [(i + 1, p.extract_text() or '') for i, p in enumerate(r.pages)]


def grep(pdf_path, word, before=0, after=0, limit=40):
    """그 말이 나오는 쪽을 찾는다. PDF 몇 번째 장인지 함께 돌려준다."""
    hits = []
    for n, t in pages(pdf_path):
        if word in t:
            hits.append((n, t))
            if len(hits) >= limit:
                break
    return hits


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    art = sys.argv[1]
    board = 55
    if '--board' in sys.argv:
        board = int(sys.argv[sys.argv.index('--board') + 1])
    m = article(art, board)
    print(f"제목   {m['title']}")
    print(f"게시   {m['posted']}   최종수정 {m['revised']}")
    print(f"담당   {m['office']}   연락처 {m['tel']}")
    print(f"주소   {m['url']}")
    for i, f in enumerate(m['files']):
        print(f"  [{i}] {f['name'] or '(이름 미상)'}  {f['url']}")
    if '--pdf' in sys.argv or '--grep' in sys.argv:
        which = 0
        if '--file' in sys.argv:
            which = int(sys.argv[sys.argv.index('--file') + 1])
        p = download(m, which)
        print(f"\n내려받음 {p}  ({os.path.getsize(p):,}B)")
        pg = pages(p)
        print(f"쪽수 {len(pg)}")
        if '--grep' in sys.argv:
            word = sys.argv[sys.argv.index('--grep') + 1]
            hits = grep(p, word)
            print(f"'{word}' 가 나오는 쪽 {len(hits)}개: {[n for n, _ in hits][:30]}")


if __name__ == '__main__':
    main()
