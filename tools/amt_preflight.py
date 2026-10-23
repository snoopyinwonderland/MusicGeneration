"""선택 실행하는 AMT 로딩 검사. 생성 실험이나 청취 평가가 아닙니다."""
import argparse
import json
import os
from pathlib import Path
import time
from importlib.metadata import version

MODEL = 'stanford-crfm/music-small-800k'
REVISION = 'fa800530aa1126dd6b58b38f3bdb8fcec9c9d4f5'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='기존 캐시만 사용')
    parser.add_argument('--threads', type=int, default=6)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('--threads는 1 이상이어야 합니다')
    # 모델 의존성은 별도 환경에서 이 명령을 실행할 때만 불러옵니다.
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    import torch
    from transformers import AutoModelForCausalLM

    root = Path(__file__).resolve().parents[1]
    out = root / 'output'
    out.mkdir(exist_ok=True)
    torch.set_num_threads(args.threads)
    start = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, cache_dir=out / 'hf-cache',
        trust_remote_code=False, local_files_only=args.offline,
    ).cpu().eval()
    loaded = time.perf_counter() - start
    with torch.inference_mode():
        # AMT의 anticipation 표지와 C4 1초 사건. 생성 샘플이 아닌 전방 계산.
        probe = model(torch.tensor([[55027, 0, 10100, 11060]])).logits
    expected = [1, 4, 55028]
    if list(probe.shape) != expected or not torch.isfinite(probe).all():
        raise RuntimeError('모델 출력 차원 또는 유한값 검사 실패')
    report = {
        'model': MODEL, 'revision': REVISION, 'license': 'apache-2.0',
        'parameters': sum(p.numel() for p in model.parameters()),
        'versions': {name: version(name) for name in
                     ('torch', 'transformers', 'huggingface-hub', 'numpy', 'mido', 'tqdm')},
        'device': str(model.device), 'cuda_available': torch.cuda.is_available(),
        'threads': args.threads, 'load_seconds': loaded,
        'offline': args.offline, 'probe_shape': list(probe.shape),
        'finite_logits': True, 'status': 'setup_verified_only',
        'generation_count': 0, 'selection_required': True,
        'generation_seconds': None, 'generation_peak_memory_bytes': None,
        'rejected_count': None, 'blind_user_choice': None,
    }
    target = out / ('preflight-offline.json' if args.offline else 'preflight.json')
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
