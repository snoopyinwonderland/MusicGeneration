"""Render the aggregate JSON without accessing lyrics or scores."""
import argparse
from html import escape
import json
from pathlib import Path

LABEL = {'affection':'애정','longing':'그리움','loss':'이별·슬픔','joy':'기쁨','isolation':'외로움','hope':'희망','unmarked':'단서 없음'}
FEATURES = {'note_count':('구간의 음표 수',1,'개'),'range_st':('음역',1,'반음'),'net_rise_st':('첫음→끝음',1,'반음'),
            'onsets_per_beat':('발음 밀도',1,'음/박'),'ending_beats':('끝음 길이',1,'박'),
            'leap_share':('5반음 이상 도약',100,'%p'),'repeat_share':('같은 음 진행',100,'%p'),
            'minor_chord_onset_share':('단화음 위 발음',100,'%p'),
            'root_plus5_share':('근음 +5 진행',100,'%p'),'chord_changes_per_beat':('화음 변화',1,'회/박')}


def table(head,rows):
    header=''.join('<th>'+escape(str(cell))+'</th>' for cell in head)
    body=''.join('<tr>'+''.join('<td>'+escape(str(cell))+'</td>' for cell in row)+'</tr>' for row in rows)
    return '<div class="scroll"><table><thead><tr>'+header+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def report(data):
    c=data['coverage']
    html=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>가사 단서와 선율·화성</title><style>body{max-width:1100px;margin:2em auto;padding:0 1em;color:#263c38;font:16px/1.65 system-ui}section,details{margin:2em 0}.scroll{overflow:auto}table{border-collapse:collapse}td,th{border-bottom:1px solid #ccc;padding:5px 12px;text-align:right;white-space:nowrap}th{background:#eef4f1}td:first-child{text-align:left}#detection td,#detection th{text-align:left;white-space:normal;min-width:6em;vertical-align:top}#detection table{width:100%}</style><main><h1>노래방 가사 단서와 선율·화성</h1>']
    cues=json.loads(Path(__file__).with_name('karaoke_lyric_cues.json').read_text('utf8'))
    html.append('<section id="detection"><h2>가사에서 어떤 단서를 찾나</h2>'
                '<p>주선율과 음절 시작 시점이 일치하는 가사 줄을 검사한다. 한글 사이 공백을 지운 뒤 아래 표현이 포함되면 해당 단서로 센다. '
                '영어 표현은 대소문자를 구별하지 않고 단어 경계에서 찾는다. 한 줄에 여러 단서가 잡힐 수 있다.</p>')
    html.append(table(['단서','한글 표현','영어 표현','검출 줄 · 한글 포함','검출 줄 · 한글 없이 라틴 문자 포함'],
                      [(LABEL[k],', '.join(v['ko']),', '.join(v['en']),f"{c['ko/'+k+'/lines']:,}",
                        f"{c['latin/'+k+'/lines']:,}") for k,v in cues.items()]))
    html.append('<p>예를 들어 ‘보 고 싶 어’는 ‘보고싶어’로 읽어 그리움으로 센다. ‘보고 싶지 않아’도 같은 표현을 포함하므로 검출된다. '
                '이 수치는 어휘의 출현을 보여 준다. 부정과 실제 청취 정서는 별도 판단이 필요하다.</p>'
                '<h2>악보에서 무엇을 한 건으로 세나</h2>')
    html.append(table(['특징','검출 조건','악보 예시 → 집계값'],[
        ('선율 윤곽','연속 네 음에서 이웃한 음의 높이를 세 번 비교','파♯–라–시–라 → 상승·상승·하강 (++−)'),
        ('음정 묶음','0·±1·±2반음은 그대로, 3–4반음과 5반음 이상은 방향별로 묶음','같은 네 음 → +3~4 / +2 / −2'),
        ('리듬 묶음','네 음 각각의 시작부터 끝까지 잰 음가를 분류','½·½·½·2박 → s/s/s/l'),
        ('윤곽과 발음 간격','세 음정의 방향과 이웃한 시작 시점 사이의 세 간격을 함께 기록','같은 네 음을 반 박마다 시작 → ++- sss'),
        ('근음 이동','명시된 인접 화음의 다음 근음에서 앞 근음을 뺀 뒤 12로 나눈 나머지','D→A는 +7, A→D는 +5'),
        ('화음 연결','해석 가능한 두 이웃 화음의 종류와 근음 이동을 함께 기록','A7→D → dominant7 +5 major'),
    ]))
    html.append('<p>s는 ½박 이하, m은 ½박 초과 1박 이하, l은 1박 초과다. 네 음 창은 채택된 가사 줄 안에서 한 음씩 옮긴다. '
                '화음 연결은 양쪽 화음을 모두 읽을 수 있는 인접 쌍마다 한 건이다.</p></section><h2>분석에 포함한 자료</h2>')
    html.append(table(['집계 대상','수'],[(label,f'{c[k]:,}') for k,label in [
        ('files','전체 MIDI 파일'),('source_excluded','기존 선율 품질 기준 제외 파일'),('files_with_text','S1 가사가 있는 유효 파일'),
        ('files_analyzed','비교 가능한 줄이 있는 파일'),('files_with_cue','정서 단서가 검출된 분석 파일'),
        ('text_lines','비어 있지 않은 원본 가사 줄'),('text_other','한글·라틴 문자 없음'),('unaligned','발음 시점 불일치'),
        ('short_or_rap','4음 미만 또는 랩 의심 구간'),('overlap_or_long_gap','음 겹침 또는 2박 이상 쉼'),
        ('duplicate_lines','같은 파일 내 동일 가사·상대 선율·리듬·화성 재출현'),('analyzed_lines','채택한 가사 줄'),('cue_lines','단서가 있는 채택 줄')]]))
    html.append('<p>원본 S1의 CP949 가사 줄 첫 음절부터 마지막 음절의 발음까지 비교했다. 한 줄에 여러 단서가 있으면 각 집단에 포함한다. 단서가 없는 줄에도 정서가 있을 수 있다. 한글이 섞인 줄은 한글 집단에 포함했다. 라틴 문자만으로 언어를 확정할 수 없다.</p>')
    for script,title in [('ko','한글 포함'),('latin','한글 없이 라틴 문자 포함')]:
        html.append(f'<section><h2>{title}</h2><p>차이는 같은 파일에서 단서 줄 평균에서 같은 문자권의 무표지 줄 평균을 뺀 값이다. 각 파일에 같은 가중치를 주었다. ±는 파일별 차이의 표준오차다. 화음 지표마다 유효 분모가 다르다.</p>')
        for name,(label,mult,unit) in FEATURES.items():
            rows=[]
            for cat,caption in LABEL.items():
                group=f'{script}/{cat}'
                v=data['metrics'].get(group,{}).get(name)
                if not v:continue
                delta='—' if v['paired_se'] is None else f"{mult*v['difference']:+.3f} ± {mult*v['paired_se']:.3f}"
                matched='—' if not v['matched_files'] else f"{mult*v['matched_difference']:+.3f} ({v['matched_files']:,})"
                rows.append([caption,c.get(group+'/lines',0),v['files'],f"{mult*v['mean']:.3f}",v['pairs'],delta,matched])
            html.append(f'<details{" open" if name=="range_st" else ""}><summary>{label} ({unit})</summary>'+table(['단서','전체 채택 줄','지표 유효 파일','파일 평균','대응 파일','파일 내 차이','동일 음표 수 차이 (파일 수)'],rows)+'</details>')
        html.append('<h3>네 음 묶음과 화성 연결</h3><p>각 가사 줄의 연속 네 음 창을 한 음씩 옮겨 집계했다. 아래는 창 수 가중 상위 세 가지와 해당 집단의 출현 비율이다. 리듬은 음가 ½박 이하(s), 1박 이하(m), 1박 초과(l)다. 윤곽은 상승·반복·하강, 음형은 방향을 보존한 반음 거리다. 근음 이동은 12로 나눈 나머지이며 미해석 화음을 건너 연결하지 않았다.</p>')
        for family,label in [('rhythm4','음가 묶음'),('contour4','윤곽'),('melody4','음정 묶음'),('timed_shape','윤곽과 발음 간격 묶음'),('root_motion','근음 이동'),('harmony','화음 종류와 근음 연결')]:
            rows=[]
            for cat,caption in LABEL.items():
                v=data['patterns'].get(f'{script}/{cat}',{}).get(family)
                if not v or not v['total']:continue
                top=list(v['counts'].items())[:3]
                rows.append([caption,f"{v['total']:,}",' · '.join(f'{k} ({100*n/v["total"]:.1f}%)' for k,n in top)])
            html.append(f'<details><summary>{label}</summary>'+table(['단서','관측 수','상위 3개'],rows)+'</details>')
        html.append('</section>')
    html.append('<p>부정·반어·화자·서사 전환을 판별하지 않은 어휘 기반 탐색이다. 원곡 장단조와 청취자의 정서 평가는 별도 검증이 필요하다. 파일 간 중복과 장르, 후렴 위치는 통제하지 않았다.</p></main></html>')
    return '\n'.join(html)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('statistics',type=Path)
    p.add_argument('html',type=Path)
    args=p.parse_args()
    args.html.write_text(report(json.loads(args.statistics.read_text('utf8'))),encoding='utf8')
