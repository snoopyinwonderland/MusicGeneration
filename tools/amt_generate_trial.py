"""Run the frozen 16-seed diagnostic using local AMT weights and source only."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musigen.model_trial import MODEL, REVISION, SOURCE_REVISION, assess, summarize, protocol


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def peak_memory():
    if os.name != 'nt':
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
            'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    value = Counters(); value.cb = ctypes.sizeof(value)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not fn(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(value), value.cb):
        raise ctypes.WinError()
    return value.PeakWorkingSetSize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error('기존 시험 결과를 덮어쓰지 않습니다. 새 출력 폴더를 사용하세요')
    revision = subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != SOURCE_REVISION:
        p.error('AMT 원본 소스 revision이 다릅니다')
    if subprocess.check_output(['git', '-C', str(args.source), 'status', '--porcelain'], text=True).strip():
        p.error('AMT 원본 소스에 변경이 있습니다')
    spec = protocol()
    inputs = json.loads(args.input.read_text(encoding='utf-8'))
    if inputs['protocol'] != spec:
        p.error('입력과 실행 프로토콜이 다릅니다')
    args.out.mkdir(parents=True)
    dump(args.out/'protocol.json', spec)
    dump(args.out/'input.json', inputs)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    sys.path.insert(0, str(args.source))
    import torch
    from transformers import AutoModelForCausalLM
    from anticipation import sample, ops
    from anticipation.convert import events_to_midi
    from anticipation.vocab import NOTE_OFFSET, DUR_OFFSET, CONTROL_OFFSET, REST
    torch.set_num_threads(6)
    t = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION,
             cache_dir=args.cache, trust_remote_code=False, local_files_only=True).cpu().eval()
    load_seconds = time.perf_counter()-t
    original_add_token = sample.add_token
    reports = []
    for seed in spec['seeds']:
        torch.manual_seed(seed)
        begun = time.perf_counter()
        sampled = []
        completed = True
        failure = None
        def bounded(*positional, **kwargs):
            if time.perf_counter()-begun > spec['seconds_per_candidate']:
                raise TimeoutError('사전 지정 120초 제한')
            if len(sampled) >= spec['max_events']:
                raise RuntimeError('사전 지정 384사건 제한')
            token = original_add_token(*positional, **kwargs)
            sampled.append(token)
            return token
        sample.add_token = bounded
        try:
            raw = sample.generate(model, spec['start_tick']/100, spec['end_tick']/100,
                  inputs=inputs['prefix_tokens'].copy(), controls=inputs['control_tokens'].copy(),
                  top_p=spec['top_p'])
        except (TimeoutError, RuntimeError) as exc:
            completed, failure = False, str(exc)
            raw = inputs['prefix_tokens'] + [v for triplet in sampled
                    if triplet[0] < spec['end_tick'] for v in triplet]
        finally:
            sample.add_token = original_add_token
        rows = [{'tick': t, 'duration': d-DUR_OFFSET, 'program': (n-NOTE_OFFSET)//128,
                 'pitch': (n-NOTE_OFFSET)%128}
                for t, d, n in zip(raw[::3], raw[1::3], raw[2::3])
                if t >= spec['start_tick'] and n != REST]
        assessment = assess(rows, spec, completed)
        dest = args.out/f'candidate-{seed+1:02d}'; dest.mkdir()
        dump(dest/'raw_tokens.json', raw)
        dump(dest/'raw_continuation.json', rows)
        full = ops.combine(ops.sort(raw), inputs['control_tokens'])
        events_to_midi(full).save(str(dest/'raw_with_fixed_harmony.mid'))
        report = dict(seed=seed, elapsed_seconds=time.perf_counter()-begun,
            peak_working_set_bytes=peak_memory(), memory_scope='process_peak_through_this_candidate',
            completed=completed, failure=failure, assessment=assessment)
        dump(dest/'report.json', report); reports.append(report)
        dump(args.out/'progress.json', reports)
        print(json.dumps({'candidate': seed+1, 'seconds': round(report['elapsed_seconds'], 2),
              'completed': completed, 'reasons': assessment['reasons']}, ensure_ascii=False), flush=True)
        if failure and 'out of memory' in failure.lower():
            dump(args.out/'stopped_memory.json', report)
            return
    summary = summarize(reports, spec)
    summary.update(model=MODEL, revision=REVISION, source_revision=revision, device='cpu', threads=6,
                   input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                   load_seconds=load_seconds, total_generation_seconds=sum(r['elapsed_seconds'] for r in reports),
                   peak_working_set_bytes=peak_memory(), selected_phrase=False)
    dump(args.out/'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
