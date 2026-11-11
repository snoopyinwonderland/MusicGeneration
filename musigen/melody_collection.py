"""Local listening collection of verified studio deliveries; no generation call."""
import argparse
import html
import json
from pathlib import Path
from musigen.studio_delivery import catalog


def write(root, selection, output='studies.html'):
    root=Path(root)
    if Path(output).name != output or not output.endswith('.html'):
        raise ValueError('Collection output must be a local HTML filename')
    available={r['id']:r for r in catalog(root) if r['status']=='draft_ready'}
    cards=[]
    esc=lambda s:html.escape(str(s),quote=True)
    for number,item in enumerate(selection,1):
        row=available.get(item['request_id'])
        if row is None:
            raise ValueError('A selected delivery is missing or has changed')
        result,pref=row['result'],row['preferences']
        links=result['outputs'];piano=links.get('piano_solo',links['melody_harmony'])
        downloads=[]
        for kind,label in [('piano_solo','피아노 솔로'),('melody_harmony','멜로디 + 상세 화성')]:
            if kind not in links:continue
            out=links[kind]
            filename=esc(result['title']+' - '+label)
            downloads.append(f'<div class="download"><a href="{esc(out["url"])}">{label}</a><span><a href="{esc(out["xml"])}" download="{filename}.musicxml">XML</a><a href="{esc(out["pdf"])}" download="{filename}.pdf">PDF</a></span></div>')
        beat='점4분음표' if pref['meter']=='6/8' else '♩'
        tempo=pref['tempo']*2/3 if pref['meter']=='6/8' else pref['tempo']
        colors=['#718775','#b29469','#6e8a99','#ad7765','#87758d']
        cards.append(f'''<article style="--accent:{colors[(number-1)%len(colors)]}"><div class="number">{number:02}</div><div class="content"><p class="facts">{esc(pref['meter'])} · {beat}={tempo:g} · {pref['bars']}마디</p><h2>{esc(result['title'])}</h2><p class="description">{esc(item['description'])}</p><p class="detail">{esc(item['listen_for'])}</p><a class="play" href="{esc(piano['url'])}">악보 보며 듣기 <span>↗</span></a><div class="downloads">{''.join(downloads)}</div><a class="plan" href="{esc(result['url'])}">곡의 흐름과 상세 화성 →</a></div></article>''')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>다섯 개의 새 문장 | MUSICANOTE Virtual Composer</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f1e9;color:#28332d;font:16px/1.65 system-ui,-apple-system,"Malgun Gothic",sans-serif}a{color:inherit;text-underline-offset:4px}header,main,footer{max-width:1120px;margin:auto;padding:26px 32px}.nav{display:flex;justify-content:space-between;gap:24px;border-bottom:1px solid #d7d8cc;padding-bottom:22px}.brand{font-size:12px;letter-spacing:.13em;font-weight:750}.nav a{font-size:13px}.hero{padding:65px 0 42px;max-width:760px}.eyebrow{font-size:13px;color:#677969;letter-spacing:.16em}.hero h1{font-family:Georgia,"Malgun Gothic",serif;font-size:58px;letter-spacing:-.065em;line-height:1.2;font-weight:500;margin:18px 0 26px}.hero p{max-width:620px;font-size:18px;color:#59675d}.tags{display:flex;gap:10px;flex-wrap:wrap}.tags span{font-size:12px;border:1px solid #cbd2c3;border-radius:30px;padding:7px 12px}main{padding-top:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}article{display:flex;gap:20px;background:#fffdf7;border-top:4px solid var(--accent);border-radius:3px 3px 14px 14px;padding:28px 25px;box-shadow:0 5px 20px #263a2a07}article:last-child{grid-column:1/-1}.number{font:italic 30px Georgia;color:var(--accent);line-height:1.4}.content{flex:1;min-width:0}.facts{font-size:12px;color:#6c796e;margin:2px 0 8px}h2{font-size:25px;font-weight:600;letter-spacing:-.04em;margin:0 0 14px}.description{color:#58665b;min-height:53px;font-size:15px}.detail{font-size:13px;color:#697366;min-height:42px}.play{display:flex;justify-content:space-between;align-items:center;padding:12px 17px;background:#345846;color:white;text-decoration:none;border-radius:7px;font-size:14px;font-weight:600;margin:22px 0 18px}.play:hover{background:#244b36}.downloads{font-size:12px}.download{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid #e6e6da}.download span{display:flex;gap:15px}.plan{display:inline-block;font-size:12px;margin-top:17px;color:#536e5d}footer{padding-top:32px;padding-bottom:45px;font-size:13px;color:#667267}footer p{max-width:820px}a:focus-visible{outline:3px solid #ba8b39;outline-offset:4px}@media(max-width:720px){header,main,footer{padding-left:20px;padding-right:20px}.hero{padding:38px 0 30px}.hero h1{font-size:40px}.hero p{font-size:16px}.grid{grid-template-columns:1fr}article{padding:22px 18px;gap:15px}article:last-child{grid-column:auto}.description,.detail{min-height:0}.nav{flex-wrap:wrap;gap:10px}.brand{font-size:11px}h2{font-size:24px}}
</style><header><nav class="nav"><span class="brand">MUSICANOTE VIRTUAL COMPOSER</span><a href="index.html">모티프 입력 →</a></nav><section class="hero"><div class="eyebrow">MELODY STUDIES · 01—05</div><h1>다섯 개의 새 문장</h1><p>짧은 모티프에서 출발해, 주제가 돌아오고 새로운 문장으로 이어지는 피아노 소품입니다. 같은 주선율을 상세 화성 악보와 피아노 솔로로 들어 보세요.</p><div class="tags"><span>주제의 재현과 변형</span><span>다양한 화성의 색채</span><span>필요한 곳에만 페달</span></div></section></header><main><section class="grid">CARDS</section></main><footer><p>대화에서 새로 작성한 다섯 곡의 연구 초안입니다. 기존 자료의 선율 관찰과 musicomp 반주 라이브러리를 참고했습니다. 자동 검사와 청취 평가는 구분하며, 이번 곡의 청취 검수는 아직 받지 않았습니다.</p><p><a href="study-report.html">제작 노트와 자료 비교 검사</a> · <a href="index.html">내 모티프로 작곡 요청하기</a></p></footer></html>'''
    target=root/output;target.write_text(page.replace('CARDS',''.join(cards)),encoding='utf-8')
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='검증한 작곡 결과의 로컬 감상 모음')
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--selection',required=True,type=Path)
    args=parser.parse_args()
    print(write(args.root,json.loads(args.selection.read_text(encoding='utf-8'))))
