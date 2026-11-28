#!/bin/sh
cd "$(dirname "$0")"
echo "=== 3B timing $(date +%T)"
python longlingua.py --model Qwen/Qwen2.5-3B --dtype bfloat16 --mode timing --ratios 0.5 --max-points 1 2>&1 | grep -E '^\{|Error'
python -c "import psutil;print('avail GB',round(psutil.virtual_memory().available/2**30,1))"
for spec in "openai-community/gpt2 float32 0.25,0.5,0.75" "Qwen/Qwen2.5-0.5B bfloat16 0.25,0.5,0.75" "Qwen/Qwen2.5-1.5B bfloat16 0.5"; do
  set -- $spec
  echo "=== quality $1 $2 $3 $(date +%T)"
  python longlingua.py --model "$1" --dtype "$2" --mode quality --types recall --ratios "$3" 2>&1 | grep -E '^\{|Error'
done
echo "=== end $(date +%T)"
