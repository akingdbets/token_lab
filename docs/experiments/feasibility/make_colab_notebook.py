"""Colab 노트북(ll_colab.ipynb, 같은 폴더) 생성. 셀 원문은 아래 문자열이 원본이다.

python docs/experiments/feasibility/make_colab_notebook.py
"""
import json
from pathlib import Path

INTRO = """# LongLLMLingua 압축 (Colab GPU)

Colab 에서는 **압축만** 한다. API 키는 쓰지도 올리지도 않는다.

순서
1. 런타임 → 런타임 유형 변경 → **GPU (T4 이상)**
2. Google Drive 의 `MyDrive/token_lab_ll/` 폴더에 `ll_inputs_samples.jsonl` 업로드 (recall 6턴, 비율 3개 = 18건)
3. 셀 1 → 셀 2 실행. 셀 2 맨 위 `MODEL` 만 바꿔 0.5B → 1.5B → 7B 차례로 다시 실행
4. 셀 3 으로 건수 확인. Drive 의 `run2/ll_outputs_<모델>.jsonl` 을 노트북 PC 의 `results/feasibility/` 로 가져온다

결과는 **건마다** Drive 에 바로 기록한다. 세션이 끊기면 셀 1·2 를 다시 실행하면 끝난 건은 건너뛰고 이어 간다.
"""

CELL1 = r'''# 셀 1: 설치와 Drive 연결
# 이미 불러온 패키지를 같은 세션에서 다시 설치하면 모듈이 꼬인다 (bitsandbytes 'functional' 오류).
# 그래서 없을 때만 설치한다. 그래도 꼬이면: 런타임 -> 세션 다시 시작 후 셀 1부터
import importlib.util, subprocess, sys
_need = [p for p, m in (("llmlingua==0.2.2", "llmlingua"), ("bitsandbytes", "bitsandbytes")) if importlib.util.find_spec(m) is None]
if _need:
    subprocess.run([sys.executable, "-m", "pip", "-q", "install", *_need], check=True)
from google.colab import drive
drive.mount("/content/drive")
import os, torch, transformers
WORK = "/content/drive/MyDrive/token_lab_ll"
os.makedirs(WORK, exist_ok=True)
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "없음 (런타임 유형을 GPU 로 바꾸세요)")
print("GPU 메모리 GB:", round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1) if torch.cuda.is_available() else 0)
print("transformers", transformers.__version__, "| torch", torch.__version__)
print("입력 파일:", os.path.exists(f"{WORK}/ll_inputs_samples.jsonl"))
'''

CELL2 = r'''# 셀 2: 압축 (MODEL 만 바꿔 다시 실행)
MODEL = "Qwen/Qwen2.5-0.5B"      # "Qwen/Qwen2.5-0.5B" -> "Qwen/Qwen2.5-1.5B" -> "Qwen/Qwen2.5-7B"
LOAD = "auto"                    # "auto" | "fp16" | "8bit" | "4bit"
                                 #   auto: 모델 무게(fp16)가 GPU 메모리의 60% 를 넘으면 8bit 로 로드 (T4 의 7B -> 8bit)
                                 #   PPL_CHUNK 로 나눠 계산하므로 메모리는 대부분 모델 무게다. 그래도 OOM 이면 "4bit" 로 바꾸거나 PPL_CHUNK 를 512 로 줄인다
INPUTS = f"{WORK}/ll_inputs_samples.jsonl"
RATIOS = [0.25, 0.5, 0.75]
PPL_CHUNK = 1024                 # 다음 토큰 확률을 이 토큰 수씩 나눠 계산 (결과는 같고 GPU 메모리가 일정해진다)
RUN = "run2"                     # 결과 폴더: WORK/run2/ (나눠 계산하기 전 결과와 섞지 않는다)

import gc, json, logging, os, time
import torch
logging.getLogger("bitsandbytes").setLevel(logging.ERROR)   # 같은 경고가 호출마다 찍히는 것을 막는다
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from llmlingua import PromptCompressor

# 이전 모델이 남아 있으면 GPU 메모리를 비운다 (모델을 바꿔 다시 실행할 때)
for _name in ("pc",):
    if _name in globals():
        del globals()[_name]
gc.collect(); torch.cuda.empty_cache()


def to_cache(pkv):
    """llmlingua 0.2.2 는 KV 를 [(k, v), ...] 로 다룬다. 새 transformers 는 Cache 객체를 쓴다."""
    from transformers import DynamicCache
    if hasattr(DynamicCache, "from_legacy_cache"):
        return DynamicCache.from_legacy_cache(tuple(pkv))
    return DynamicCache(ddp_cache_data=[(k, v) for k, v in pkv])


def to_legacy(cache):
    if hasattr(cache, "layers"):
        return [(l.keys, l.values) for l in cache.layers]
    if hasattr(cache, "to_legacy_cache"):
        return list(cache.to_legacy_cache())
    return [(k, v) for k, v in zip(cache.key_cache, cache.value_cache)]


class KVCompat:
    def __init__(self, model):
        self.__dict__["m"] = model

    def __getattr__(self, n):
        return getattr(self.m, n)

    def __call__(self, *a, past_key_values=None, **kw):
        from transformers import Cache
        if past_key_values is not None and not isinstance(past_key_values, Cache):
            past_key_values = to_cache(past_key_values)
        out = self.m(*a, past_key_values=past_key_values, **kw)
        if out.past_key_values is not None and isinstance(out.past_key_values, Cache):
            out.past_key_values = to_legacy(out.past_key_values)
        return out


def pick_load(model_name):
    if LOAD != "auto":
        return LOAD
    cfg = AutoConfig.from_pretrained(model_name)
    h, n, v, inter = cfg.hidden_size, cfg.num_hidden_layers, cfg.vocab_size, cfg.intermediate_size
    params = n * (4 * h * h + 3 * h * inter) + 2 * v * h      # 대략치
    gpu = torch.cuda.get_device_properties(0).total_memory
    return "8bit" if params * 2 > 0.6 * gpu else "fp16"


class GPUCompressor(PromptCompressor):
    """llmlingua 의 load_model 대신 직접 로드 (8bit/4bit 선택, KV 형식 변환)."""

    def load_model(self, model_name, device_map="cuda", model_config={}):
        mode = pick_load(model_name)
        cfg = AutoConfig.from_pretrained(model_name)
        tok = AutoTokenizer.from_pretrained(model_name)
        tok.padding_side = "left"
        tok.pad_token_id = cfg.pad_token_id if cfg.pad_token_id else tok.eos_token_id
        kw = {"device_map": {"": 0}}
        if mode == "fp16":
            kw["torch_dtype"] = torch.float16
        elif mode == "8bit":
            kw["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            kw["torch_dtype"] = torch.float16    # 양자화 안 되는 층도 fp16 (T4 는 bf16 이 느리고, 안 주면 매 호출 경고가 쏟아진다)
        elif mode == "4bit":
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                                                           bnb_4bit_quant_type="nf4")
            kw["torch_dtype"] = torch.float16
        model = AutoModelForCausalLM.from_pretrained(model_name, **kw).eval()
        self.load_mode = mode
        self.device = "cuda"
        self.tokenizer = tok
        self.model = KVCompat(model)
        self.context_idxs = []
        self.max_position_embeddings = cfg.max_position_embeddings

    def get_ppl(self, text, granularity="sentence", input_ids=None, attention_mask=None, past_key_values=None,
                return_kv=False, end=None, condition_mode="none", condition_pos_id=0):
        """llmlingua 0.2.2 get_ppl 과 같은 값을 PPL_CHUNK 토큰씩 나눠 계산한다.
        원래 코드는 새 토큰 전체의 logits(토큰 수 x 어휘 15만)를 한 번에 만들어 긴 기록에서 메모리가 넘친다."""
        from transformers import Cache, DynamicCache
        if input_ids is None:
            enc = self.tokenizer(text, return_tensors="pt")
            input_ids = enc["input_ids"].to(self.device)
            attention_mask = enc["attention_mask"].to(self.device)
        past_length = past_key_values[0][0].shape[2] if past_key_values is not None else 0
        if end is None:
            end = input_ids.shape[1]
        end = min(end, past_length + self.max_position_embeddings)
        cache = to_cache(past_key_values) if past_key_values is not None else DynamicCache()
        loss_fct = torch.nn.CrossEntropyLoss(reduction="none")
        losses = []
        with torch.no_grad():
            for s in range(past_length, end, PPL_CHUNK):
                e = min(s + PPL_CHUNK, end)
                out = self.model.m(input_ids[:, s:e], attention_mask=attention_mask[:, :e], past_key_values=cache,
                                   use_cache=True)
                cache = out.past_key_values
                last = min(e, end - 1)              # 위치 s..last-1 이 다음 토큰 s+1..last 를 예측
                if last > s:
                    logits = out.logits[0, : last - s]
                    labels = input_ids[0, s + 1: last + 1]
                    active = attention_mask[0, s:last] == 1
                    losses.append(loss_fct(logits[active], labels[active]))
                del out
        loss = torch.cat(losses) if losses else torch.zeros(0, device=input_ids.device)
        if condition_mode == "before":
            loss = loss[:condition_pos_id]
        elif condition_mode == "after":
            loss = loss[condition_pos_id:]
        res = loss.mean() if granularity == "sentence" else loss
        if return_kv:
            return res, (to_legacy(cache) if isinstance(cache, Cache) else cache)
        return res


tag = MODEL.split("/")[-1]
os.makedirs(f"{WORK}/{RUN}", exist_ok=True)
OUT = f"{WORK}/{RUN}/ll_outputs_{tag}.jsonl"
ERR = f"{WORK}/{RUN}/ll_errors_{tag}.jsonl"
done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        r = json.loads(line)
        done.add((r["scenario"], r["turn"], r["ratio"]))
items = [json.loads(l) for l in open(INPUTS, encoding="utf-8")]
todo = [(x, r) for x in items for r in RATIOS if (x["scenario"], x["turn"], r) not in done]
print(f"{MODEL}: 전체 {len(items) * len(RATIOS)}건, 끝남 {len(done)}건, 남음 {len(todo)}건")

if todo:
    t0 = time.perf_counter()
    pc = GPUCompressor(model_name=MODEL, device_map="cuda")
    print("로드", pc.load_mode, f"{time.perf_counter() - t0:.0f}초, GPU 사용 {torch.cuda.memory_allocated() / 2**30:.1f}GB")
    tok = lambda s: len(pc.tokenizer.encode(s, add_special_tokens=False))
    gpu_name = torch.cuda.get_device_name(0)
    for x, r in todo:
        total = sum(tok(t) for t in x["all_texts"])
        recent = sum(tok(m["content"]) for m in x["recent"])
        target = int(total * r) - recent
        torch.cuda.reset_peak_memory_stats()
        t1 = time.perf_counter()
        try:
            if target <= 0 or not x["contexts"]:
                res = {"compressed_prompt": "", "origin_tokens": 0, "compressed_tokens": 0}
            else:
                res = pc.compress_prompt(x["contexts"], instruction="", question=x["question"], target_token=target,
                                         rank_method="longllmlingua", condition_in_question="after_condition",
                                         reorder_context="original", dynamic_context_compression_ratio=0.3,
                                         condition_compare=True, context_budget="+100", concate_question=False,
                                         use_sentence_level_filter=False)
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            with open(ERR, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"scenario": x["scenario"], "turn": x["turn"], "ratio": r, "model": MODEL,
                                     "load": pc.load_mode, "error": "OOM", "detail": str(e)[:300]}) + "\n")
            print(x["scenario"], x["turn"], r, "메모리 부족(OOM): 건너뜀. PPL_CHUNK 를 512 로 줄이거나 LOAD=4bit 로 다시 실행하면 이 건만 다시 한다")
            continue
        sec = time.perf_counter() - t1
        row = {"scenario": x["scenario"], "turn": x["turn"], "ratio": r, "model": MODEL, "load": pc.load_mode,
               "gpu": gpu_name, "ppl_chunk": PPL_CHUNK, "target_tokens_model": target, "origin_tokens_model": res.get("origin_tokens"),
               "compressed_tokens_model": res.get("compressed_tokens"), "seconds": round(sec, 2),
               "max_gpu_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
               "compressed_prompt": res["compressed_prompt"]}
        with open(OUT, "a", encoding="utf-8") as fh:          # 건마다 Drive 에 바로 기록
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush(); os.fsync(fh.fileno())
        print(x["scenario"], x["turn"], r, f"{sec:.1f}초, GPU 최대 {row['max_gpu_gb']}GB")
    print("끝", f"{time.perf_counter() - t0:.0f}초")
'''

CELL3 = r'''# 셀 3: 결과 확인 (파일은 이미 Drive 에 건마다 저장돼 있다)
import glob, json, os
for path in sorted(glob.glob(f"{WORK}/run2/ll_outputs_*.jsonl")):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    keys = {(r["scenario"], r["turn"], r["ratio"]) for r in rows}
    secs = sorted(r["seconds"] for r in rows)
    print(os.path.basename(path), f"{len(keys)}/18건", "| 로드", {r["load"] for r in rows},
          "| 1회 초: 중앙", secs[len(secs) // 2] if secs else "-", "최대", secs[-1] if secs else "-",
          "| GPU 최대", max((r["max_gpu_gb"] for r in rows), default="-"), "GB")
for path in sorted(glob.glob(f"{WORK}/run2/ll_errors_*.jsonl")):
    print("오류 기록:", os.path.basename(path), sum(1 for _ in open(path, encoding="utf-8")), "줄")
# 노트북 PC 로 받을 때: Drive 에서 직접 내려받거나 아래 줄의 주석을 풀어 브라우저로 받는다
# from google.colab import files; [files.download(p) for p in glob.glob(f"{WORK}/run2/ll_outputs_*.jsonl")]
'''


def cell(kind, src):
    c = {"cell_type": kind, "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}
    if kind == "code":
        c.update({"execution_count": None, "outputs": []})
    return c


nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "cells": [cell("markdown", INTRO), cell("code", CELL1), cell("code", CELL2), cell("code", CELL3)]}
out = Path(__file__).resolve().parent / "ll_colab.ipynb"
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(out)
