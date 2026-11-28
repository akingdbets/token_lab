#!/bin/sh
# 모델별 시간 측정을 하나씩 (동시에 돌리지 않음)
cd "$(dirname "$0")"
for spec in "openai-community/gpt2 float32" "Qwen/Qwen2.5-0.5B float32" "Qwen/Qwen2.5-0.5B bfloat16" "Qwen/Qwen2.5-1.5B float32" "Qwen/Qwen2.5-1.5B bfloat16"; do
  set -- $spec
  echo "=== $1 $2 $(date +%T)"
  python longlingua.py --model "$1" --dtype "$2" --mode timing --ratios 0.5 2>&1 | grep -E '^\{|Error|error' 
  python -c "import psutil;print('avail GB',round(psutil.virtual_memory().available/2**30,1))"
done
