#!/usr/bin/env bash
# Run all benchmarks matching DR-Tulu's evaluation setup.
#
# Usage:
#   bash evals/scripts/run_all.sh              # full run (all examples)
#   bash evals/scripts/run_all.sh --quick      # quick run (5 examples each)
#
# Prerequisites:
#   pip install -e evals/
#   export OPENAI_API_KEY=...   # for grading (gpt-4.1-mini)
#   claude, paper, paper-search must be on PATH

set -euo pipefail
cd "$(dirname "$0")/../.."

MODEL="${MODEL:-sonnet}"
MAX_TURNS="${MAX_TURNS:-15}"
THREADS="${THREADS:-10}"
SKILL="${SKILL:-deep-research}"
OUTPUT_DIR="${OUTPUT_DIR:-evals/results}"

# Parse --quick flag
NUM_FLAG=""
if [[ "${1:-}" == "--quick" ]]; then
    NUM_FLAG="-n 5"
    echo "=== Quick mode: 5 examples per benchmark ==="
fi

echo "=== Config: model=$MODEL  max_turns=$MAX_TURNS  threads=$THREADS  skill=$SKILL ==="
echo "=== Output: $OUTPUT_DIR ==="
echo ""

# ─── ResearchQA (100 examples, auto-downloads from HuggingFace) ───
echo ">>> ResearchQA"
python -m evals.run run -b researchqa \
    -m "$MODEL" --max-turns "$MAX_TURNS" --threads "$THREADS" \
    --skill "$SKILL" --output-dir "$OUTPUT_DIR" $NUM_FLAG
echo ""

# ─── HealthBench — all subsets (366 / 183 / 183 examples, auto-downloads) ───
for subset in all hard consensus; do
    echo ">>> HealthBench ($subset)"
    python -m evals.run run -b healthbench --subset "$subset" \
        -m "$MODEL" --max-turns "$MAX_TURNS" --threads "$THREADS" \
        --skill "$SKILL" --output-dir "$OUTPUT_DIR" $NUM_FLAG
    echo ""
done

# ─── SQA v2 (100 examples, auto-downloads from allenai/asta-bench) ───
echo ">>> SQA v2"
python -m evals.run run -b sqa \
    -m "$MODEL" --max-turns "$MAX_TURNS" --threads "$THREADS" \
    --skill "$SKILL" --output-dir "$OUTPUT_DIR" $NUM_FLAG
echo ""

# ─── DRB (100 examples, auto-downloads from rl-research/deep_research_bench_eval) ───
echo ">>> DRB"
python -m evals.run run -b drb \
    -m "$MODEL" --max-turns "$MAX_TURNS" --threads "$THREADS" \
    --skill "$SKILL" --output-dir "$OUTPUT_DIR" $NUM_FLAG
echo ""

echo "=== All benchmarks complete. Results in $OUTPUT_DIR ==="
ls -lh "$OUTPUT_DIR"/*.json "$OUTPUT_DIR"/*.jsonl 2>/dev/null || true
