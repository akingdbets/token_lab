"""LongLLMLingua 후보 모델 다운로드 (safetensors·설정·토크나이저만)."""
import sys, time
from huggingface_hub import snapshot_download
for rid in sys.argv[1:]:
    t = time.time()
    try:
        p = snapshot_download(rid, allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "merges.txt", "vocab.*"])
        print(f"OK {rid} {time.time()-t:.0f}s {p}", flush=True)
    except Exception as e:
        print(f"FAIL {rid} {type(e).__name__}: {e}", flush=True)
