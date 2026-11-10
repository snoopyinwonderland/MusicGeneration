"""Read-only local corpus discovery, observations, and composer context lookup.

python -m musigen.corpus_catalog inventory --out output/corpus
python -m musigen.corpus_catalog observe --out output/corpus
python -m musigen.corpus_catalog query --out output/corpus --composer handel
All outputs are local audit/reference artifacts; generation defaults are untouched.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata
import zipfile

from .corpus_features import digest, xml_features, voice_observations, midi_features

DATA = Path(__file__).parent / 'data' / 'composer_context.json'
XML = {'.xml', '.musicxml', '.mxl'}
MIDI = {'.mid', '.midi', '.kar'}
ANNOTATIONS = {'.tsv', '.rntxt', '.jams', '.lab'}
NOTATION = {'.krn', '.ly', '.mscx', '.mscz', '.gp5', '.gp4', '.gpx', '.mei'}
AUDIO = {'.mp3', '.wav', '.flac', '.ogg', '.m4a'}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if not unicodedata.combining(c)).strip()


def resolve_composer(path, creators, contexts):
    # Full-name aliases only. "Bach" must never collapse C.P.E. into J.S. Bach.
    name = Path(path).stem.split('_')[0]
    xml_names = [x.get('text') or '' for x in creators if x.get('type') == 'composer']
    def matches(text):
        clean = norm(text)
        return {c['id'] for c in contexts if clean in {norm(a) for a in c['aliases']}}
    filename_ids = matches(name)
    xml_ids = set().union(*(matches(s) for s in xml_names)) if xml_names else set()
    if filename_ids and xml_ids and filename_ids != xml_ids:
        return {'id': None, 'label': name, 'basis': 'conflict', 'raw_xml': xml_names}
    ids = filename_ids or xml_ids
    if len(ids) == 1:
        return {'id': next(iter(ids)), 'label': name, 'basis': 'filename_full_name' if filename_ids else 'xml_full_name', 'raw_xml': xml_names}
    # Retain other full-name dataset labels, without fabricating historical identity.
    if re.match(r'^[^,\d]+,\s+[^\d]+$', name):
        return {'id': 'unverified:' + norm(name), 'label': name, 'basis': 'unverified_filename', 'raw_xml': xml_names}
    return {'id': None, 'label': name, 'basis': 'unknown', 'raw_xml': xml_names}


def discover_sources():
    result = []
    def add(ident, path, family, purpose, recursive=True):
        result.append({'id': ident, 'path': str(path), 'family': family, 'purpose': purpose,
                       'recursive': recursive, 'generation_default': False,
                       'rights_state': 'source_and_score_terms_require_review'})
    base = Path('K:/MusicSearch/data')
    for folder, family, purpose in [
        ('classical-corpora','classical','score_structure_harmony_or_performance'),
        ('pop-and-analysis-corpora','pop-analysis','melody_harmony_form'),
        ('global-pop-midi','global-midi','arrangement_rhythm_performance'),
        ('jazz-corpora','jazz','melody_harmony_improvisation'),
        ('guitar-corpora','guitar','rhythm_voicing_instrument_specific'),
        ('korean-traditional-music','traditional','rhythm_modal_techniques'),
    ]:
        p = base / folder
        if p.exists():
            for child in sorted(p.iterdir()):
                if child.is_dir() and not child.name.startswith('.'):
                    add(f'{folder}/{child.name}', child, family, purpose)
    root = Path('K:/Music Analysis/MusicXML')
    add('local-musicxml/root',root,'mixed-scores','paired_arrangements_leadsheets',False)
    if root.exists():
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name != '__MACOSX':
                add(f'local-musicxml/{child.name}',child,'mixed-scores','notated_voice_patterns')
    extra = Path('K:/Music Composition/data/external')
    if extra.exists():
        for child in sorted(extra.iterdir()):
            if child.is_dir():
                add(f'composition-external/{child.name}',child,'annotated-motifs','motif_phrase_boundaries')
    for ident,path,family,purpose in [
        ('musicomp-knowledge','K:/Music Composition/musicomp/knowledge/data','derived','existing_models_patterns_splits'),
        ('analysis-corpus','K:/Music Analysis/corpus','evaluation','do_not_mix_gold_or_quarantine_into_training'),
        ('pdmx-mxl','K:/mxl','mixed-scores','large_score_collection'),
        ('pdmx-search-xml','U:/MusicSearch-PDMX','derived','search_copy_not_new_unique_works'),
        ('kysing-xml','U:/KYSing_MusicXML','karaoke','lyric_melody_harmony_alignment'),
        ('kysing-metadata','K:/MusicSearch/data/kysing-metadata','metadata','song_ids_titles_credits'),
        ('aihub-gugak','K:/Korean Traditional Music Data','traditional','score_audio_alignment'),
        ('chopin-folder','K:/Chopin','scores','additional_score_editions'),
        ('musicanote-data','K:/MUSICANOTE/data','mixed-scores','additional_scores'),
    ]:
        add(ident,Path(path),family,purpose)
    return result


def source_files(source):
    root = Path(source['path'])
    if not root.exists():
        return []
    if not source['recursive']:
        return sorted(p for p in root.iterdir() if p.is_file())
    args = ['rg','--files','--null','--hidden','--no-ignore',str(root)]
    for directory in ('.git','node_modules','__pycache__','__MACOSX','.venv'):
        args += ['-g',f'!**/{directory}/**']
    r = subprocess.run(args,capture_output=True,encoding='utf-8')
    if r.returncode not in (0,1):
        raise RuntimeError(r.stderr[:500])
    return sorted(Path(x) for x in r.stdout.split('\0') if x)


def inventory(out):
    out.mkdir(parents=True,exist_ok=True)
    sources = discover_sources()
    with gzip.open(out/'files.jsonl.gz','wt',encoding='utf-8') as dst:
        for source in sources:
            files = source_files(source)
            suffixes = Counter(p.suffix.lower() for p in files)
            source.update(exists=Path(source['path']).exists(),files=len(files),extensions=dict(suffixes),
                          musicxml=sum(suffixes[e] for e in XML),midi=sum(suffixes[e] for e in MIDI),
                          other_notation=sum(suffixes[e] for e in NOTATION),
                          annotations=sum(suffixes[e] for e in ANNOTATIONS),
                          audio=sum(suffixes[e] for e in AUDIO))
            # Retain local license/readme locations, not a guessed license inheritance.
            source['documentation'] = [str(p) for p in files if re.match(r'^(readme|licen[sc]e|copying|disclaimer)',p.name,re.I)][:30]
            for p in files:
                dst.write(json.dumps({'source':source['id'],'path':str(p),'extension':p.suffix.lower()},ensure_ascii=False)+'\n')
            print(f"{source['id']}: XML={source['musicxml']}, MIDI={source['midi']}, files={len(files)}",flush=True)
    write_json(out/'inventory.json',{'created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'explicit local music corpus roots, archives counted as containers; not all disks',
        'counts_are':'files, not unique works; XML extension alone does not certify score content',
        'sources':sources})


def observe(out, midi_limit=32):
    inv = json.loads((out/'inventory.json').read_text(encoding='utf-8'))
    contexts = json.loads(DATA.read_text(encoding='utf-8'))['composers']
    files = defaultdict(list)
    with gzip.open(out/'files.jsonl.gz','rt',encoding='utf-8') as src:
        for line in src:
            r = json.loads(line)
            if r['extension'] in XML|MIDI:
                files[r['source']].append(Path(r['path']))
    profiles, seen, coverage = {}, {}, []
    selected_xml = {f'local-musicxml/{n}' for n in ('utf8','Mozart','Beethoven','Chopin')}
    with gzip.open(out/'bars.jsonl.gz','wt',encoding='utf-8') as bars, \
         (out/'observations.jsonl').open('w',encoding='utf-8') as log:
        for source in inv['sources']:
            sid = source['id']
            candidates = files[sid]
            xmls = [p for p in candidates if p.suffix.lower() in XML] if sid in selected_xml else []
            midis = [p for p in candidates if p.suffix.lower() in MIDI]
            # Stable hash sample prevents sorted-title sampling; never claim census.
            midis.sort(key=lambda p: digest(str(p.relative_to(source['path'])).encode()))
            # Project data contract: locate/count these sources, but do not mine
            # AI Hub/KY musical content until its permitted use is established.
            metadata_only = source['family'] in ('traditional','karaoke')
            selected_midi = [] if metadata_only else (midis if midi_limit == 0 else midis[:midi_limit])
            cov = {'source':sid,'xml_attempted':len(xmls),'midi_available':len(midis),
                   'midi_attempted':len(selected_midi),'content_policy':'metadata_only' if metadata_only else 'local_inspection',
                   'ok':0,'failed':0,'byte_duplicates':0}
            for p in xmls+selected_midi:
                rec = {'source':sid,'path':str(p),'state':'inspection_only_unpartitioned',
                       'generation_eligible':False}
                try:
                    before = p.stat()
                    sha = digest(p.read_bytes()); rec['sha256'] = sha
                    if sha in seen:
                        rec['duplicate_of'] = seen[sha];cov['byte_duplicates'] += 1
                    elif p.suffix.lower() in XML:
                        meta, rows = xml_features(p)
                        comp = resolve_composer(p,meta['creators'],contexts)
                        rec.update(format='musicxml',metadata=meta,composer=comp,part_bars=len(rows))
                        key = comp['id'] or 'unknown'
                        pr = profiles.setdefault(key,{'files':0,'part_bars':0,'voice_bars':0,
                            'attacks':0,'monophonic_voice_bars':0,'explicit_rest_quarters':'0',
                            'meters':Counter(),'durations':Counter(),'intervals':Counter(),
                            'harmony_events':0,'xml_lyrics':0,'context':next((c for c in contexts if c['id']==key),None)})
                        # Check the input has not changed before counting a successful parse.
                        after = p.stat()
                        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                            raise ValueError('source_changed_during_read')
                        pr['files'] += 1
                        for row in rows:
                            observations = voice_observations(row)
                            pr['part_bars'] += 1
                            pr['meters'][row['meter'] or 'unknown'] += 1
                            pr['harmony_events'] += len(row['harmony'])
                            pr['xml_lyrics'] += sum(n['lyrics_count'] for n in row['notes'])
                            for v in observations:
                                pr['voice_bars'] += 1;pr['attacks'] += v['attacks']
                                pr['monophonic_voice_bars'] += v['monophonic']
                                pr['explicit_rest_quarters'] = str(Fraction(pr['explicit_rest_quarters'])+Fraction(v['explicit_rest_quarters']))
                                pr['durations'].update(v['durations']);pr['intervals'].update(v['intervals'])
                            bars.write(json.dumps({'source':sid,'file_sha256':sha,'composer':comp,
                                'generation_eligible':False,'row':row,'voices':observations},ensure_ascii=False)+'\n')
                    else:
                        rec.update(format='midi',observations=midi_features(p))
                        after = p.stat()
                        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                            raise ValueError('source_changed_during_read')
                    if 'duplicate_of' not in rec:
                        seen[sha] = str(p)
                    cov['ok'] += 1
                except Exception as e:
                    rec['error'] = f'{type(e).__name__}: {e}'
                    cov['failed'] += 1
                log.write(json.dumps(rec,ensure_ascii=False)+'\n')
            coverage.append(cov)
            if xmls or selected_midi:
                print(cov,flush=True)
    for p in profiles.values():
        p['mean_attacks_per_voice_bar'] = round(p['attacks']/p['voice_bars'],4) if p['voice_bars'] else None
    write_json(out/'style-profiles.json',{'state':'descriptive_reference_not_trained_generator',
        'sampling':'all utf8 and Mozart/Beethoven/Chopin XML; unique bytes within analyzed set',
        'limits':['file identity is not work identity','all notated parts, not piano-only',
                  'XML pitches are written pitches; instrument transposition is not applied',
                  'intervals only within monophonic voice-bars','no automatic melody/harmony/cadence labels',
                  'unpartitioned observations must not enter generation/evaluation training'],
        'profiles':profiles})
    write_json(out/'coverage.json',{'midi_limit_per_source':midi_limit,'sources':coverage})


def query(out, composer=None, era=None, region=None, active_at=None):
    profiles=json.loads((out/'style-profiles.json').read_text(encoding='utf-8'))['profiles']
    result={}
    for name, profile in profiles.items():
        context=profile.get('context') or {}
        if composer and norm(composer) not in norm(name+' '+json.dumps(context,ensure_ascii=False)):
            continue
        if era and era not in context.get('era_tags_editorial',[]):
            continue
        if region and norm(region) not in norm(' '.join(context.get('activity_regions',[]))):
            continue
        if active_at is not None and not any(a['years'][0]<=active_at<=a['years'][1]
                                            for a in context.get('documented_activity',[])):
            continue
        result[name]=profile
    return {'use':'conversation planning reference; not automatic style composition', 'profiles':result}


def metadata(out):
    """Source-owned work context and native splits, not guessed identity joins."""
    out.mkdir(parents=True,exist_ok=True)
    ypath=Path('K:/MusicSearch/data/classical-corpora/ycacl/YCACL_Metadata.csv')
    with ypath.open(encoding='utf-8-sig',newline='') as src:
        rows=list(csv.DictReader(src))
    with gzip.open(out/'work-contexts.jsonl.gz','wt',encoding='utf-8') as dst:
        for i,row in enumerate(rows,2):
            dst.write(json.dumps({'source':'YCACL_Metadata.csv','row':i,
                'semantics':'source labels: Nationality is not birthplace; Range is not verified activity dates',
                'raw':row,'joined_to_local_score':False},ensure_ascii=False)+'\n')
    mp=Path('K:/MusicSearch/data/classical-corpora/maestro-piano-midi/maestro-v3.0.0/maestro-v3.0.0.csv')
    with mp.open(encoding='utf-8-sig',newline='') as src:
        performances=list(csv.DictReader(src))
    write_json(out/'native-performance-splits.json',{'source':str(mp),'sha256':digest(mp.read_bytes()),
        'note':'year is recording competition year, not composition year', 'rows':performances})
    pop=Path('K:/MusicSearch/data/pop-and-analysis-corpora/pop909/POP909')
    canonical=list(pop.glob('[0-9][0-9][0-9]/[0-9][0-9][0-9].mid'))
    giant=Path('K:/MusicSearch/data/classical-corpora/giant-midi-piano')
    gp=giant/'metadata.csv'
    with gp.open(encoding='utf-8-sig',newline='') as src:
        giant_rows=list(csv.DictReader(src,delimiter='\t')) # .csv name, TSV content
    ids={p.stem for p in (giant/'midis').glob('*.mid')}
    # audio_name already has NO extension. Path.stem would truncate names with
    # catalog dots (e.g. Op.27); keep sanitized mismatches visible as unmatched.
    matched=[r for r in giant_rows if r['audio_name'] in ids]
    counts=Counter(r['audio_name'] for r in matched)
    with gzip.open(out/'giant-midi-contexts.jsonl.gz','wt',encoding='utf-8') as dst:
        for row in matched:
            dst.write(json.dumps({'source':'GiantMIDI metadata.csv','raw':row,
                'local_midi':str(giant/'midis'/(row['audio_name']+'.mid')),
                'match':'exact_audio_name','ambiguous':counts[row['audio_name']]!=1,
                'biography_verified':False,'generation_eligible':False},ensure_ascii=False)+'\n')
    archives=[]
    for path in sorted(Path('K:/').glob('*.zip')):
        if not any(x in path.name.casefold() for x in ('chopin','kysing','소나타','musicxml','infringement')):
            continue
        try:
            with zipfile.ZipFile(path) as z:
                names=[x.filename for x in z.infolist() if not x.is_dir() and '__MACOSX/' not in x.filename]
            archives.append({'path':str(path),'members':len(names),
                             'extensions':dict(Counter(Path(n).suffix.lower() for n in names)),
                             'content':'archive_inventory_only_not_extracted'})
        except (OSError,zipfile.BadZipFile) as e:
            archives.append({'path':str(path),'error':str(e)})
    result={'ycacl':{'path':str(ypath),'sha256':digest(ypath.read_bytes()),'rows':len(rows),
        'composer_labels':len({r['Composer'] for r in rows}),
        'nationality_labels':dict(Counter(r['Nationality'] for r in rows)),
        'genre_labels':dict(Counter(r['Genre'] for r in rows))},
        'maestro':{'performances':len(performances),'native_splits':dict(Counter(r['split'] for r in performances))},
        'pop909':{'canonical_midi_files':len(canonical),'versions_are_not_new_songs':True},
        'giant_midi':{'metadata_path':str(gp),'metadata_sha256':digest(gp.read_bytes()),
            'catalog_rows':len(giant_rows),'local_midi_files':len(ids),
            'exact_matched_files':len(counts),'ambiguous_matches':sum(v!=1 for v in counts.values()),
            'matched_composer_name_pairs':len({(r['surname'],r['firstname']) for r in matched}),
            'unmatched_local_files':sorted(ids-set(counts)),
            'note':'catalog is larger than downloaded MIDI; birth/death/nationality remain source claims, not activity/birthplace'},
        'archives':archives}
    write_json(out/'metadata-summary.json',result)
    return result


def variation_id(stem):
    # The optional content letter is absent in some releases. Keep its absence;
    # it is not evidence that all those phrases are the same musical material.
    m=re.fullmatch(r'([BM][A-Za-z0-9]{3})_(\d+)_(\d+)([a-z]*)_([a-z])',stem)
    return m.groups() if m else None


def motif_map(out):
    """Index documented theme/variation relationships without flattening annotators."""
    root=Path('K:/MusicSearch/data/classical-corpora/tavern')
    works=defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    unmatched=[]
    for p in sorted(root.rglob('*.krn')):
        if p.parent.name!='Joined':
            continue
        ident=variation_id(p.stem)
        if not ident:
            unmatched.append(str(p));continue
        work,variation,phrase,content,annotator=ident
        data=p.read_bytes()
        header=next((line for line in data.decode('utf-8-sig',errors='replace').splitlines() if line.startswith('**')),None)
        works[work][variation][phrase+content][annotator]={'path':str(p),'sha256':digest(data),'spines':header}
    mapped={k:dict(v) for k,v in works.items()}
    bp=Path('K:/Music Composition/data/external/bps_motif')
    bps=[]
    for p in sorted((bp/'csv_label').glob('*.csv')):
        with p.open(encoding='utf-8-sig',newline='') as src:
            rows=list(csv.DictReader(src))
        notes=bp/'csv_notes'/p.name
        bps.append({'movement':p.stem,'labels':str(p),'labels_sha256':digest(p.read_bytes()),
                    'notes':str(notes),'notes_exist':notes.exists(),'rows':rows,
                    'time_contract':'source onset in quarter units; motif_midi QPM=60 and contains motifs only'})
    result={'state':'reference_addresses_not_verified_cross_variation_note_alignment',
            'tavern':{'works':mapped,'unmatched_joined_paths':unmatched,
                      'theme_variation_id':'00','annotators_kept_separate':True},'bps':bps}
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/'motif-development-map.json',result)
    summary={'tavern_work_groups':len(mapped),
             'tavern_theme_phrases':sum(len(v.get('00',{})) for v in mapped.values()),
             'tavern_variation_groups':sum(sum(k!='00' for k in v) for v in mapped.values()),
             'tavern_variation_phrases':sum(len(ph) for v in mapped.values() for k,ph in v.items() if k!='00'),
             'tavern_unmatched_joined':len(unmatched),'bps_movements':len(bps),
             'bps_annotation_rows':sum(len(b['rows']) for b in bps),
             'bps_notes_missing':sum(not b['notes_exist'] for b in bps)}
    write_json(out/'motif-map-summary.json',summary)
    return summary


def summarize(out):
    inv=json.loads((out/'inventory.json').read_text(encoding='utf-8'))
    cov=json.loads((out/'coverage.json').read_text(encoding='utf-8'))
    profiles=json.loads((out/'style-profiles.json').read_text(encoding='utf-8'))['profiles']
    errors=Counter();midi=defaultdict(Counter);byte_duplicates=0;xml_parsed=0
    with (out/'observations.jsonl').open(encoding='utf-8') as src:
        for line in src:
            row=json.loads(line)
            if row.get('error'): errors[row['error']]+=1
            if row.get('duplicate_of'): byte_duplicates+=1
            if row.get('format')=='musicxml':xml_parsed+=1
            if row.get('format')=='midi':
                m=midi[row['source']];o=row['observations'];m['parsed_unique_files']+=1
                m['files_with_note_warnings']+=bool(o['warnings'])
                m['files_with_explicit_meter']+=bool(o['meters'])
                for t in o['tracks']:
                    for k in ('pitched_notes','drum_notes','lyrics_events','pedal_events'):m[k]+=t[k]
    result={'roots':len(inv['sources']),'files':sum(s['files'] for s in inv['sources']),
        'musicxml_extensions':sum(s['musicxml'] for s in inv['sources']),
        'midi_extensions':sum(s['midi'] for s in inv['sources']),
        'xml_attempted':sum(s['xml_attempted'] for s in cov['sources']),
        'unique_xml_parsed':xml_parsed,'midi_attempted':sum(s['midi_attempted'] for s in cov['sources']),
        'unique_midi_parsed':sum(m['parsed_unique_files'] for m in midi.values()),
        'byte_duplicates':byte_duplicates,'errors':dict(errors),
        'composer_groups_including_unknown':len(profiles),
        'context_verified_groups':sum(bool(p['context']) for p in profiles.values()),
        'part_bars':sum(p['part_bars'] for p in profiles.values()),
        'voice_bars':sum(p['voice_bars'] for p in profiles.values()),
        'attacks':sum(p['attacks'] for p in profiles.values()),
        'scope':'inspection only; file counts are not unique work counts; no new generator trained'}
    result['xml_pitch_basis']='written_not_concert'
    write_json(out/'summary.json',result)
    write_json(out/'midi-profiles.json',{'sampling_limit_per_source':cov['midi_limit_per_source'],
        'state':'sample_observations_not_population_estimates','sources':dict(midi)})
    lines=['# 로컬 작곡 자료 조사 결과','',
        '파일·파트 마디·성부 마디는 서로 다른 단위입니다. 원자료의 새 학습/생성 투입 완료 보고가 아닙니다.','',
        '```json',json.dumps(result,ensure_ascii=False,indent=2),'```','',
        '## 자료 위치별 파일 수','',
        '| 자료 위치 | XML 계열 | MIDI/KAR | 기타 기보 | 주석 확장자 |',
        '|---|---:|---:|---:|---:|']
    for s in inv['sources']:
        lines.append(f"| {s['id']} | {s['musicxml']} | {s['midi']} | {s['other_notation']} | {s['annotations']} |")
    lines+=['','## 작곡가별 관찰','',
        '바이트 중복 제거 후, 여러 편성의 파트·성부를 합친 관찰입니다. 독주용 목표값이 아닙니다.','',
        '| 이름 그룹 | 파일 | 파트 마디 | 성부 마디 | 음 공격 | 평균 공격/성부 마디 |',
        '|---|---:|---:|---:|---:|---:|']
    for name,p in sorted(profiles.items(),key=lambda item:-item[1]['files']):
        label=(p.get('context') or {}).get('name_ko',name)
        lines.append(f"| {label} | {p['files']} | {p['part_bars']} | {p['voice_bars']} | {p['attacks']} | {p['mean_attacks_per_voice_bar']} |")
    (out/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description='로컬 음악 자료 목록·관찰 통계')
    p.add_argument('command',choices=['inventory','observe','metadata','motif-map','summary','query'])
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--midi-limit',type=int,default=32,help='코퍼스별 검사 파일 수, 0이면 전수')
    p.add_argument('--composer');p.add_argument('--era');p.add_argument('--region')
    p.add_argument('--active-at',type=int,help='확인된 활동 구간에 포함된 연도만 필터')
    args=p.parse_args()
    if args.midi_limit < 0:
        p.error('midi-limit must be >= 0')
    if args.command=='inventory': inventory(args.out)
    elif args.command=='observe': observe(args.out,args.midi_limit)
    elif args.command=='metadata': print(json.dumps(metadata(args.out),ensure_ascii=False,indent=2))
    elif args.command=='motif-map': print(json.dumps(motif_map(args.out),ensure_ascii=False,indent=2))
    elif args.command=='summary': print(json.dumps(summarize(args.out),ensure_ascii=False,indent=2))
    else: print(json.dumps(query(args.out,args.composer,args.era,args.region,args.active_at),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
