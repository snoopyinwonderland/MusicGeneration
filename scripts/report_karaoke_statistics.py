"""Produce a Korean, aggregate-only report from the completed local census."""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import sqlite3


def report(root):
    progress=json.loads((root/'progress.json').read_text(encoding='utf8'))
    if progress.get('phase')!='complete' or progress.get('remaining')!=0:
        raise ValueError('A completed census is required; do not publish partial results')
    data=json.loads((root/'statistics.json').read_text(encoding='utf8'))
    db=sqlite3.connect((root/'statistics.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'))
    def counter(family):
        return dict(db.execute('SELECT pattern,occurrences FROM patterns WHERE family=?',(family,)))
    def pct(n,d): return f'{100*n/d:.2f}%' if d else '분모 없음'
    sections=[]
    def section(title,paragraph,heads,rows):
        sections.append((title,paragraph,heads,[[str(x) for x in r] for r in rows]))
    coverage=data['coverage'];m=data['song_metrics'];unique=data['deduplication']['melody_unique_files']
    error_counts=Counter(e for e, in db.execute("SELECT error FROM files WHERE status='error'"))
    rap_files=db.execute("SELECT COUNT(*) FROM song_metrics WHERE json_extract(metrics,'$.excluded_rap_suspect')>0").fetchone()[0]
    zero_files=db.execute("SELECT COUNT(*) FROM song_metrics WHERE json_extract(metrics,'$.attacks')=0").fetchone()[0]
    section('범위와 분모','원본 MIDI를 전수 시도했다. 파생 MusicXML을 새 곡으로 더하지 않았다. 파일과 독립 작품의 수는 다르다.',
            ['항목','수'],[['원본 대상',manifest['files']],['읽기 성공',coverage.get('ok',0)],['검토 대상으로 제외',coverage.get('error',0)],
                          ['미처리',manifest['files']-sum(coverage.values())],['전체 선율 지문 중복 제거 후',unique],
                          ['화성까지 같은 자료의 중복 제거 후',data['deduplication']['harmony_unique_files']],
                          ['원 주선율 음수',m['raw_attacks']['sum']],['랩 자리표시 의심 제외 음수',m['excluded_rap_suspect']['sum']],
                          ['남은 음수',m['attacks']['sum']],['랩 의심 구간이 있는 지문',rap_files],['제외 후 선율이 없는 지문',zero_files]])
    section('제외 사유','S1/channel 4가 확실하지 않거나 다성·잘못된 음가·상충 메타데이터가 있는 파일은 임의 수정하지 않았다.',
            ['사유','파일 수'],error_counts.most_common())
    rows=[];interval_summary={}
    classes=[('같은 음',lambda x:x==0),('반음·온음',lambda x:0<abs(x)<=2),('3–4반음',lambda x:3<=abs(x)<=4),('5반음 이상 도약',lambda x:abs(x)>=5)]
    for family,label in [('raw_interval','원본 전체 · 랩 포함'),('interval_all_gaps','랩 제외 · 긴 쉼 포함'),('interval','랩 제외 · 1박 미만 쉼으로 연결')]:
        c=counter('melody.'+family);den=sum(c.values());interval_summary[family]={'denominator':den}
        for name,fn in classes:
            n=sum(v for k,v in c.items() if fn(int(k)));interval_summary[family][name]=n
            rows.append([label,name,f'{n:,} / {den:,}',pct(n,den)])
    section('음정 분포','주된 음형 집계는 랩 의심 구간·음 겹침·1박 이상의 쉼을 건너뛰지 않는다. 원본 전체 수치는 비교용이다.',
            ['범위','진행','음정 쌍','비율'],rows)
    section('곡마다 같은 비중으로 보면','노트 수가 많은 곡의 영향과 구별한다. 각 선율의 비율을 먼저 구한 뒤 평균했다.',
            ['관찰','해당 선율 수','곡별 비율 평균','중앙값'],
            [[{'interval_step_fraction':'반음·온음','interval_repeat_fraction':'같은 음','interval_leap_fraction':'5반음 이상'}[k],v['n'],pct(v['mean'],1),pct(v['median'],1)]
             for k,v in data['equal_song_weight'].items() if k in ('interval_step_fraction','interval_repeat_fraction','interval_leap_fraction')])
    context_path=root/'block-context.json'
    if context_path.exists():
        context=json.loads(context_path.read_text(encoding='utf8'))
        if context['totals']['unique_melodies']!=unique:
            raise ValueError('Block-context census coverage differs')
        rows=[]
        for field,label in [('all_two_bar_intervals','2마디 창 전체'),('unique_two_bar_intervals','곡 안 같은 2마디를 한 번씩')]:
            c=context[field];den=sum(c.values())
            for name,fn in classes:
                n=sum(v for k,v in c.items() if fn(int(k)));rows.append([label,name,den,pct(n,den)])
        section('후렴·구절의 반복 횟수를 줄여 세면','동일하게 채택된 2마디 창끼리 비교한다. 상대 음높이+정확한 리듬이 같은 창을 곡 안에서 한 번만 센 결과다. 곡 전체와는 구간 범위가 다르다.',
                ['가중 방식','진행','음정 쌍 분모','비율'],rows)
        section('명시 조표와 박자의 구성','중요: 분석 대상의 MIDI 장·단조 비트가 모두 0(major)이다. major_only는 원본 표기일 뿐 실제 곡이 모두 장조라는 뜻이 아니다. 이 비트로 실제 장단조·종지 기능을 판정하지 않는다. 박자는 한 곡에 여러 개면 각각 지지 수에 포함한다.',
                ['종류','선율 지문 수'],list(context['explicit_key_modes'].items())+list(context['meter_document_support'].items()))
    c=counter('melody.direction_after_interval');rows=[]
    for name,label in [('step_1_2','반음·온음 뒤'),('third_3_4','3–4반음 뒤'),('leap_5_plus','5반음 이상 도약 뒤')]:
        den=sum(c.get(name+':'+v,0) for v in ('opposite','same','zero'))
        rows.append([label,den,pct(c.get(name+':opposite',0),den),pct(c.get(name+':same',0),den),pct(c.get(name+':zero',0),den)])
    section('앞 음정에 따른 다음 방향','도약 다음의 반복음도 분모에 포함한다. 반대 방향으로 진행해야 한다는 강제 규칙이 아니다.',
            ['앞 음정','후속음정 있는 쌍','역방향','같은 방향','반복음'],rows)
    durations=counter('melody.duration_quarters');total=sum(durations.values())
    section('음가','음가 단위는 4분음표=1이다. 붙임줄에 해당하는 MIDI 유지음은 하나의 발음으로 센다.',
            ['음가','음수','비율'],[[k,v,pct(v,total)] for k,v in sorted(durations.items(),key=lambda x:-x[1])[:14]])
    gaps=counter('melody.gap_quarters');positive=sum(v for k,v in gaps.items() if float_fraction(k)>0)
    section('쉼과 구간 끝의 머무름','쉼 기준 구간은 분석용 후보다. 사람의 프레이즈·가사 문장·노래방 화면 줄바꿈과 같다고 가정하지 않는다. 끝 음가 비교는 4음 이상 구간에서 앞 음가를 정렬한 중앙 순위 값(짝수 개면 위쪽 값)을 사용한다.',
            ['관찰','수치'],[
                ['양의 음 사이 간격',positive],['1박 이상 간격',sum(v for k,v in gaps.items() if float_fraction(k)>=1)],
                ['2박 이상 간격',sum(v for k,v in gaps.items() if float_fraction(k)>=2)],
                ['0.5박 기준 구간 수',m['runs_gap_half']['sum']],['1박 기준 구간 수',m['runs_gap1']['sum']],['2박 기준 구간 수',m['runs_gap2']['sum']],
                *[[f'구간 마지막 음가 / 앞 음가 중앙값 {k}',v] for k,v in counter('melody.run_end_length_ratio').items()]])
    for size in (4,6,8):
        family=f'melody.interval_pattern_{size}';d=data['families'][family]
        section(f'{size}음 음형 · 여러 곡에 나타나는 패턴','쉼으로 끊기지 않은 연속 음정이다. 숫자는 반음 단위이며 0은 반복음. 곡 내 중복을 한 번만 세는 지문별 지지 수로 정렬했다.',
                ['음정 배열','출현 횟수','지지 선율 지문 수'],[[r['pattern'],r['occurrences'],r['documents']] for r in d['top_document_support'][:10]])
    section('6음 contour와 음가의 결합','U=상행, D=하행, ==같은 음. short≤0.5박, medium<2박, long≥2박. 단순화한 음가 구간이며 원래 시각은 로컬 DB에 유지한다.',
            ['contour | 음가','출현 횟수','지지 선율 수'],[[r['pattern'],r['occurrences'],r['documents']] for r in data['families']['melody.gesture_6']['top_document_support'][:8]])
    rows=[];repetition={}
    for size in (2,4,8):
        c=counter(f'melody.block_{size}_repetition');repetition[size]=c
        for kind,label in [('pitch','상대 음높이'),('rhythm','리듬'),('joint','상대 음높이+리듬')]:
            rows.append([f'{size}마디',label,c.get(kind+'_blocks',0),c.get(kind+'_unique',0),pct(c.get(kind+'_reused_occurrences',0),c.get(kind+'_blocks',0))])
    section('긴 구간을 되풀이하는 정도','명시 박자에 맞춘 비중첩 창이다. 4발음 이상이고 경계에 걸린 음·랩·겹침이 없는 창만 비교한다. 전체 음악의 모든 프레이즈를 대표하지 않는다. 반복 비율은 각 곡에서 첫 출현을 뺀 횟수/전체 창이다.',
            ['길이','비교 요소','창 수','곡 내 중복 제거 창 수','재출현 비율'],rows)
    rows=[]
    labels={'exact':'같은 음높이·리듬','transposed':'전체 이조','same_rhythm_changed_pitch':'리듬 유지·음형 변경',
            'same_intervals_changed_rhythm':'상대 음형 유지·리듬 변경','both_changed':'두 요소 모두 변경'}
    for size in (2,4,8):
        c=counter(f'melody.block_{size}_adjacent_relation');den=sum(c.values())
        for key,v in sorted(c.items(),key=lambda x:-x[1]):rows.append([size,labels[key],v,pct(v,den)])
    section('바로 다음 묶음과의 관계','연속된 창만 비교한다. 두 요소 모두 변경됐다는 것은 공통 동기가 없다는 뜻이 아니다. 부분 변형은 완전 일치보다 넓다.',
            ['마디 수','관계','쌍 수','비율'],rows)
    rows=[]
    for size in (2,4,8):
        c=counter(f'melody.block_{size}_ending_variant');den=c.get('equal_attack_count_pairs',0);n=c.get('same_relative_first_half',0)
        rows.append([size,n,den,pct(n,den)])
    section('앞 음형을 유지하고 끝을 바꾸는 경우','발음 수가 같은 인접 창 중, 첫 절반의 상대 음높이는 같고 차이가 뒤 절반에만 있는 경우다. 리듬은 같을 필요가 없다. 모든 동기 변형을 검출한 값은 아니다.',
            ['마디 수','종결부 변형 후보','발음 수 같은 쌍','비율'],rows)
    chords=counter('harmony.chord_quality');den=sum(chords.values())
    section('원본 코드 종류','원본 Chord 트랙의 동일 연속 라벨을 합친 사건 수다. 화음 구간 길이 가중치가 아니며 추정·보강 화음은 없다. major/minor 등은 구성음에 따른 큰 분류로, 6/add 음을 가진 변형도 포함한다. 정확한 구성음별 빈도는 DB에 따로 있다.',
            ['종류','사건 수','비율'],[[k,v,pct(v,den)] for k,v in sorted(chords.items(),key=lambda x:-x[1])])
    motion=counter('harmony.root_motion');den=sum(motion.values())
    section('조성 판정에 의존하지 않는 근음 관계','다음 근음에서 앞 근음을 빼고 옥타브를 접은 반음 거리다. +5는 C→F, G→C 같은 관계이고 실제 베이스의 위아래 진행을 뜻하지 않는다.',
            ['근음 차이 mod 12','전이 수','비율'],[[k,v,pct(v,den)] for k,v in sorted(motion.items(),key=lambda x:-x[1])])
    for size in (3,4):
        family=f'harmony.degree_progression_{size}'
        section(f'{size}화음 진행','명시 조표가 같은 구간만 비교한다. 앞의 major는 모두 0인 원본 모드 비트이며 실제 장조 판정이 아니다. 숫자는 조표의 관계장조 기준음부터의 반음 거리다. 실제 으뜸음·국소 조성·기능화성·종지 정답으로 확정하지 않는다.',
                ['기보 조표 상대 진행','사건 수','지지 선율+화성 지문 수'],[[r['pattern'],r['occurrences'],r['documents']] for r in data['families'][family]['top_document_support'][:10]])
    aligned=counter('harmony.melody_alignment')
    section('선율과 화음의 관계','음이 시작할 때의 명시 코드 구성음 여부다. 비화성음은 오류가 아니며, 지속 중 화음이 바뀌는 경우의 판정은 포함하지 않는다.',
            ['분류','음수','전체 선율 음 대비'],[[k,v,pct(v,sum(aligned.values()))] for k,v in aligned.items()])
    c=counter('harmony.membership_duration');rows=[]
    for name,label in [('short','0.5박 이하'),('medium','0.5박 초과~2박 미만'),('long','2박 이상')]:
        yes=c.get(name+':True',0);no=c.get(name+':False',0)
        rows.append([label,yes+no,pct(yes,yes+no)])
    section('긴 음이 어디에 머무르는가','명시 코드가 있는 발음만 분모에 넣는다. 음가와 구성음 여부의 연관을 관찰하며 원인이나 작곡 규칙으로 확정하지 않는다.',
            ['음가','라벨 있는 음수','화음 구성음 비율'],rows)
    section('비화성음 연결 후보','같은 코드 구간에서 구성음→비구성음→구성음이고 양쪽 이동이 1–2반음일 때 경과/보조 형태를 센다. 의도·기능을 확정한 분석은 아니다.',
            ['형태','횟수'],counter('harmony.nonchord_triples').items())
    section('음역과 구절 규모','각 선율의 값 분포다. 정점은 최고음의 첫 등장이고 감정적 절정의 정답은 아니다.',
            ['관찰','10백분위','중앙값','90백분위'],[[k,m[k]['p10'],m[k]['median'],m[k]['p90']] for k in ('pitch_range','attacks','first_high_position','runs_gap1','key_changes')])
    next_steps=[
            '1. 소스 묶음을 음정·리듬·도착음·쉼·화성 문맥이 결합된 하나의 제스처로 검색한다.',
        '2. 단선율·랩 제외·박자·화성 근거를 확인한 묶음으로 후보군을 만들고, 시작/응답/고조/종결의 역할은 따로 검수한다.',
        '3. 다음 음만 뽑지 않고 묶음의 재현·음역 이동·끝부분 변형을 계획한다. 빈도를 곡의 고정 비율로 강제하지 않는다.',
        '4. 곡별 출처를 나눈 학습/검증 자료와 기존 사용자 선호 후보를 이용해, 새 방식의 청취 개선 여부를 비교한다.'
    ]
    section('이 통계를 다음 작곡에 연결하는 순서','이번 결과는 집계와 검색용 자료다. 생성기 기본값 변경·신경망 학습·청취 개선 검증은 아직 하지 않았다.',
            ['후속 단계'],[[x] for x in next_steps])
    blocks=db.execute('SELECT COUNT(*) FROM blocks').fetchone()[0]
    summary={'coverage':coverage,'unique_melodies':unique,'rap_affected_files':rap_files,'zero_after_rap':zero_files,
             'intervals':interval_summary,'block_repetition':repetition,'indexed_blocks_2_and_4':blocks,
             'alignment':aligned,'error_reasons':dict(error_counts)}
    (root/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    # Full conditional interval-transition table, with source support; no smoothing or quality claim.
    pairs=list(db.execute("SELECT pattern,occurrences,documents FROM patterns WHERE family='melody.interval_transition'"))
    denominators=Counter()
    for key,n,_ in pairs:denominators[key.split(',')[0]]+=n
    probabilities=[{'previous':int(key.split(',')[0]),'next':int(key.split(',')[1]),'count':n,'documents':d,
                    'denominator':denominators[key.split(',')[0]],'probability':n/denominators[key.split(',')[0]]} for key,n,d in pairs]
    (root/'interval-transition-probabilities.json').write_text(json.dumps(probabilities,ensure_ascii=False),encoding='utf8')
    md=['# 노래방 전체 주선율·화성 통계 — 2026-11-18','']
    body=[]
    for title,paragraph,heads,rows in sections:
        md.extend(['## '+title,'',paragraph,'','| '+' | '.join(h.replace('|',' / ') for h in heads)+' |','| '+' | '.join(['---']*len(heads))+' |'])
        md.extend('| '+' | '.join(x.replace('|',' / ') for x in row)+' |' for row in rows);md.append('')
        body.append('<section><h2>'+escape(title)+'</h2><p>'+escape(paragraph)+'</p><div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(cell)+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table></div></section>')
    (root/'report.md').write_text('\n'.join(md),encoding='utf8')
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>노래방 전체 선율 통계 · MUSICANOTE</title>
<style>body{margin:0;background:#f5f4ed;color:#20352d;font:16px/1.65 'Malgun Gothic',sans-serif}main{max-width:1080px;margin:auto;padding:30px 20px}h1{font-size:clamp(26px,4vw,42px);line-height:1.3}h2{font-size:23px}a{color:#255b45}section{margin:26px 0;padding:22px;background:#fffefa;border:1px solid #d7ded5;border-radius:12px}p{color:#506358}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid #e0e4dc;padding:9px 10px}th{background:#e8efe4}td{font-variant-numeric:tabular-nums}td:first-child{overflow-wrap:anywhere}header p{max-width:850px}.badge{display:inline-block;padding:5px 12px;background:#e8efe4;border-radius:20px;font-weight:700}.chart{display:grid;gap:10px}.bar{background:#e5ebe1;border-radius:5px;overflow:hidden}.fill{height:22px;background:#42785d}</style>
<main><header><a href="index.html">MUSICANOTE Virtual Composer · 작품 목록</a><h1>노래방 전체 주선율·화성 통계</h1><span class="badge">2026-11-18 · 로컬 전수 분석</span><p>50,874개 MIDI를 대상으로 음 하나와 음형 묶음, 여러 마디의 반복·발전, 명시 화음을 함께 조사했습니다. 랩 자리표시 의심 구간을 제외합니다. 이 빈도를 그대로 강제하는 생성 규칙은 만들지 않았습니다.</p></header>'''
    mainc=interval_summary['interval'];den=mainc['denominator']
    html+='<section><h2>구간 안에서 실제로 움직이는 음정</h2><p>랩 제외 · 1박 미만 쉼으로 연결된 음정 쌍</p><div class="chart">'
    for name,_ in classes:
        n=mainc[name];html+=f'<div>{escape(name)} · {pct(n,den)}<div class="bar"><div class="fill" style="width:{100*n/den:.3f}%"></div></div></div>'
    html=html.replace('50,874개 MIDI',f'{manifest["files"]:,}개 MIDI')
    html+='</div></section>'+''.join(body)+'<footer>전체 자료는 인기·장르별로 통제한 표본이 아닙니다. 저작권 원곡 음표와 가사 원문은 이 페이지에 포함하지 않았습니다.</footer></main></html>'
    (root/'report.html').write_text(html,encoding='utf8')
    db.close()
    print(json.dumps(summary,ensure_ascii=False))


def float_fraction(value):
    from fractions import Fraction
    return float(Fraction(value))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();report(a.root)
