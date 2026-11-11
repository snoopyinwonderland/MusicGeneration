"""Explicit piano realization of an authored blueprint using existing musicomp LH retrieval.

Melody, harmony, keys and form remain MusicGeneration's authored contract. Corpus
selection changes eligible LH figures only; it does not compose or reharmonize.
"""
import argparse
import copy
import html
import hashlib
import json
import shutil
from fractions import Fraction as F
from pathlib import Path
from musigen import MUSICOMP_ROOT
from musigen.blueprint import prepare,write_xml,verify_roundtrip,dump,digest
from musigen.checks import check
from musigen.corpus_accomp import select,FIELD
from musigen.development_comparison import signature,verify_written
from musigen.expression import playback
from musigen.functional_harmony import AUGMENTED
from musigen.listen import _write_page,_instrumentation,VEROVIO_CDN
from musigen.motif_clip import pitch_name
from musigen.piece import build,Note
from musicomp.realize.musicxml import read_parts
from musicomp.theory import tpc_name


def realize(lead,plan,score,corpus=False):
    """Validate an independent performance score before allowing LH retrieval."""
    candidate=build(plan['design'],score)
    if signature(candidate,'rh')!=signature(lead,'rh'):
        raise ValueError('피아노 실현안이 주선율의 음·음가·쉼·표현을 바꿨습니다')
    if candidate.bar_keys!=lead.bar_keys:raise ValueError('피아노 실현안의 국소 조성이 다릅니다')
    authoritative=dict(lead.analysis_chords)
    for on,ch in candidate.analysis_chords:
        if ch is None:continue  # A directly written functional chord may have no ordinary symbol.
        expected=authoritative.get(on)
        if expected is None or ch.bass_tpc!=expected.bass_tpc or set(ch.tones)!=set(expected.tones):
            raise ValueError('피아노 실현안의 반주 화성이 설계와 다릅니다')
    frozen=select(plan['design'],score) if corpus else copy.deepcopy(score)
    candidate=build(plan['design'],frozen)
    if signature(candidate,'rh')!=signature(lead,'rh'):
        raise ValueError('자료 반주 적용 후 주선율이 바뀌었습니다')
    candidate.chords=copy.deepcopy(lead.chords)
    candidate.analysis_chords=copy.deepcopy(lead.analysis_chords)
    return candidate,frozen


def preserve_prefix(piece,path,bars):
    if type(bars)is not int or not 1<=bars<=piece.bars:raise ValueError('보존 마디 범위 오류')
    parts=read_parts(path)
    if len(parts)!=1 or parts[0].staves!=2:raise ValueError('보존 기준은 한 파트 피아노 악보여야 합니다')
    previous=copy.deepcopy(piece)
    previous.notes=[Note(n.onset,n.dur,tuple(n.pitches),'rh' if n.staff==1 else 'lh',n.voice,'previous',n.articulation)
                    for n in parts[0].notes]
    end=bars*piece.bar_len
    for hand in ('rh','lh'):
        # The reader does not expose slurs; protect notes, spelling, articulation and timing.
        if [s[:-1] for s in signature(piece,hand,hi=end)]!=[s[:-1] for s in signature(previous,hand,hi=end)]:
            raise ValueError(f'보존 구간 {hand}가 달라졌습니다')
    return {'bars':[1,bars],'hands':['rh','lh'],'notes_spelling_timing_exact':True,
            'source':str(path),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def performed_harmony(piece,details):
    """Retain the complete design alongside the actual sparse LH, without conflating them."""
    rows=[]
    for e in details['events']:
        start,end=F(e['onset']),F(e['onset'])+F(e['duration'])
        notes=[n for n in piece.notes if n.hand=='lh' and n.onset<end and n.onset+n.dur>start]
        actual={t for n in notes for m,t in n.pitches}
        required={t for on,ch in piece.analysis_chords if on==start for pc,t in ch.tones}
        missing=required-actual
        rows.append({'bar':e['bar'],'offset':e['offset'],'symbol':e['symbol'],
                     'scope':'notes_overlapping_harmony_span_not_simultaneous_chord',
                     'missing_tpcs_in_played_lh':sorted(missing),
                     'missing_tone_names_in_played_lh':[tpc_name(t) for t in sorted(missing)],
                     'notes':[{'onset':str(n.onset),'duration':str(n.dur),
                               'pitches':[pitch_name(m,t) for m,t in n.pitches],'source':n.src} for n in notes]})
    return rows


def write_pages(out,plan,details,pieces,checks,feedback):
    (out/'assets').mkdir(exist_ok=True)
    shutil.copyfile(MUSICOMP_ROOT/'node_modules/verovio/dist/verovio-toolkit-wasm.js',out/'assets/verovio.js')
    titles={'melody_harmony':'멜로디 + 상세 화성','piano_solo':'피아노 솔로'}
    for kind,piece in pieces.items():
        xml=(out/(kind+'.musicxml')).read_text(encoding='utf-8');instrumentation=_instrumentation(xml)
        instrumentation['label']=titles[kind]
        harmony=[{**e['roman'],'q':float(F(e['onset'])),'bar':e['bar'],'symbol':e['symbol'],
                  'symbol_display':e['roman']['display'] if e['quality'] in AUGMENTED else None} for e in details['events']]
        pdf=out/(kind+'.pdf')
        entry={'piece':kind,'xml':xml,'design':plan['design'],'checks':checks[kind],
               'info':{'version':'v001','reason':feedback,'preserve':[],'preserve_broken':[]},
               'performance':playback(piece),'instrumentation':instrumentation,'harmony':harmony,
               '_pdf':str(pdf) if pdf.is_file() else None}
        target=out/(kind+'.html');_write_page([entry],target,None,True)
        text=target.read_text(encoding='utf-8').replace(VEROVIO_CDN,'assets/verovio.js')
        text=text.replace('<body>','<body><nav style="padding:12px 24px;background:#e6eee5"><a href="index.html">← 작품과 화성 설계</a></nav>')
        target.write_text(text,encoding='utf-8')
    esc=lambda v:html.escape(str(v))
    cards=''.join(f'<article><h2>{title}</h2><p>'+('주선율과 모든 화음 구성음을 담은 설계 악보입니다.' if k=='melody_harmony' else '기존 musicomp의 반주 자료와 직접 쓴 종지·연결부를 결합했습니다.')+
                  f'</p><a class="listen" href="{k}.html">악보 보며 듣기 →</a><p><a href="{k}.musicxml" download>XML 받기</a> · '+
                  (f'<a href="{k}.pdf" download>PDF 받기</a>' if (out/(k+'.pdf')).is_file() else 'PDF 미생성')+'</p></article>' for k,title in titles.items())
    phrases=''.join(f'<li><strong>{p["bars"][0]}–{p["bars"][1]}마디 · {esc(p["role"])}</strong><br>{esc(p["plan"])}</li>' for p in plan['design'].get('phrase_plan',[]))
    functions={'tonic':'으뜸 기능','predominant':'딸림 준비','dominant':'딸림 기능','other':'기타'}
    rows=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (e['bar'],e['offset'],e['duration'],e['roman']['key'],e['roman']['display'],e['bass'],' · '.join(e['tones']),' · '.join(e['voicing']),functions.get(e.get('function'),''),e.get('cadence','')))+'</tr>' for e in details['events'])
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TITLE | MUSICANOTE Virtual Composer</title>
<style>*{box-sizing:border-box}body{background:#f6f3eb;color:#243b32;font:16px/1.7 system-ui;margin:0}main{max-width:1140px;margin:auto;padding:44px 28px}header{border-bottom:1px solid #cbd4c5;padding-bottom:24px}.brand{letter-spacing:.12em;font-size:12px;font-weight:700}h1{font-size:42px;line-height:1.3;margin:18px 0}h2{font-size:23px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:28px 0}article{background:#fffefa;border:1px solid #d5dccf;border-radius:16px;padding:24px}.listen{display:inline-block;background:#315943;color:white;padding:10px 20px;border-radius:8px;text-decoration:none}a{color:#285c43;text-underline-offset:4px}.muted{color:#5a6b60}.plan{background:#e8eee2;border-radius:16px;padding:24px}.plan ol{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding-left:24px}.scroll{overflow:auto;background:white;padding:16px;border-radius:12px}table{border-collapse:collapse;white-space:nowrap;font-size:13px}th,td{text-align:left;border-bottom:1px solid #ddd;padding:9px}footer{font-size:13px;margin-top:26px}@media(max-width:700px){main{padding:24px 16px}.grid,.plan ol{grid-template-columns:1fr}h1{font-size:32px}}</style>
<main><header><div class="brand">MUSICANOTE VIRTUAL COMPOSER</div><h1>TITLE</h1><p>ARC</p><p class="muted">FACTS</p></header><section class="grid">CARDS</section><section class="plan"><h2>곡의 흐름</h2><ol>PHRASES</ol></section><h2>상세 왼손 화성</h2><p>전체 구성음과 기능·종지의 설계를 표시합니다. 연주용 반주의 실제 음표와 생략음은 별도 JSON에 함께 기록했습니다.</p><p><a href="harmony.json" download>상세 화성 JSON</a> · <a href="performed_harmony.json" download>피아노 반주 음표·출처 JSON</a></p><div class="scroll"><table><thead><tr><th>마디</th><th>시작</th><th>길이</th><th>국소 조성</th><th>기능 기호</th><th>베이스</th><th>전체 구성음</th><th>설계 배치</th><th>기능 의도</th><th>종지 의도</th></tr></thead><tbody>ROWS</tbody></table></div><footer><p>모티프 발전과 화성은 대화에서 작성했습니다. 반주에는 기존 musicomp 자료를 재사용했습니다. 완성곡 초안이며 새 곡에 대한 청취 평가는 아직 받지 않았습니다.</p><a href="result.json">검증 기록</a> · <a href="feedback.json">청취 의견과 제작 결정</a></footer></main></html>'''
    piece=pieces['piano_solo'];facts=f'{piece.bars}마디 · 약 {float(piece.bars*piece.bar_len)*60/piece.qpm:.0f}초 · {piece.meter} · ♩={piece.qpm:g}'
    for token,value in {'TITLE':esc(piece.title),'ARC':esc(plan['design'].get('impression',{}).get('arc','')),'FACTS':esc(facts),'CARDS':cards,'PHRASES':phrases,'ROWS':rows}.items():page=page.replace(token,value)
    (out/'index.html').write_text(page,encoding='utf-8')


def run(work,out,corpus=False,pages_only=False):
    work,out=Path(work),Path(out);read=lambda n:json.loads((work/n).read_text(encoding='utf-8'))
    motif,plan,realization=read('motif.json'),read('development.json'),read('realization.json')
    if realization.get('format')!='musicanote-piano-realization' or realization.get('version')!=1:raise ValueError('피아노 실현안 형식 오류')
    inputs=digest([motif,plan,realization]);lead,_,details=prepare(motif,plan)
    if pages_only:
        old=json.loads((out/'result.json').read_text(encoding='utf-8'))
        if old['input_sha256']!=inputs:raise ValueError('입력이 바뀌었습니다. 새 출력 폴더를 사용하세요')
        frozen=json.loads((out/'solo_score.json').read_text(encoding='utf-8'))
        solo,frozen=realize(lead,plan,frozen)
    else:
        if out.exists() and any(out.iterdir()):raise ValueError('새 출력 폴더를 지정하세요')
        solo,frozen=realize(lead,plan,realization['score'],corpus)
    preservation=None
    if realization.get('preserve'):
        p=realization['preserve'];preservation=preserve_prefix(solo,p['source'],p['bars'])
    checks={kind:check(piece,plan['design']) for kind,piece in [('melody_harmony',lead),('piano_solo',solo)]}
    if any(c['errors'] for c in checks.values()):raise ValueError(str({k:c['errors'] for k,c in checks.items()}))
    out.mkdir(parents=True,exist_ok=True);report={'input_sha256':inputs,'status':'complete_piece_draft_awaiting_listener_feedback','preservation':preservation,'files':{}}
    for kind,piece in [('melody_harmony',lead),('piano_solo',solo)]:
        target=out/(kind+'.musicxml')
        if not pages_only:write_xml(piece,target)
        report['files'][kind]=verify_roundtrip(piece,target) if kind=='melody_harmony' else verify_written(piece,target)
        dump(out/(kind+'_checks.json'),checks[kind])
    for name in ('motif.json','development.json','realization.json'):shutil.copyfile(work/name,out/name)
    dump(out/'solo_score.json',frozen);dump(out/'harmony.json',details)
    dump(out/'performed_harmony.json',performed_harmony(solo,details))
    if plan['design'].get('accompaniment_plan'):
        from musigen.accompaniment_context import observe
        dump(out/'accompaniment_context.json',observe(solo,plan['design']))
    dump(out/'feedback.json',realization['feedback'])
    if FIELD in frozen:
        dump(out/'accompaniment_report.json',frozen[FIELD]['report'])
        report['corpus_applied_bars']=frozen[FIELD]['report']['applied_bars']
    report['pedal_spans']=sum(e['kind']=='pedal' for e in solo.expression)
    dump(out/'result.json',report)
    write_pages(out,plan,details,{'melody_harmony':lead,'piano_solo':solo},checks,realization['feedback']['user_text'])
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description='모티프 발전 설계의 피아노 실현')
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--corpus-accompaniment',action='store_true');p.add_argument('--pages-only',action='store_true')
    a=p.parse_args();print(json.dumps(run(a.work,a.out,a.corpus_accompaniment,a.pages_only),ensure_ascii=False))
