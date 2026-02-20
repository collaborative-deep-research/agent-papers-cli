# Evaluation Harness

Evaluate Claude's ability to use the `paper` and `paper-search` CLI tools on academic research benchmarks.

## Benchmarks

| Benchmark | Type | Grading |
|-----------|------|---------|
| **ResearchQA** | Answer research questions | LLM coverage scoring (5-point scale) |
| **HealthBench** | Answer health/medical questions | LLM rubric scoring (criterion-met) |
| **SQAv2** | Structured QA with citations | External ASTA evaluator |
| **DRB** | Deep research reports | External RACE/FACT scoring |

## Setup

```bash
cd evals
uv pip install .

# Required API keys
export ANTHROPIC_API_KEY=...   # For Claude (generation)
export OPENAI_API_KEY=...      # For GPT-4.1-mini (grading)
```

Make sure `paper` and `paper-search` are installed and on your PATH.

## Usage

### End-to-end (generate + evaluate)

```bash
python -m evals.run run --benchmark researchqa --num-examples 5
python -m evals.run run --benchmark healthbench --subset hard --num-examples 5
```

### Generate only

```bash
python -m evals.run generate --benchmark researchqa --num-examples 10 --model claude-sonnet-4-20250514
```

### Evaluate existing generations

```bash
python -m evals.run evaluate --benchmark researchqa --generation-file evals/results/researchqa_gen.jsonl
```

### SQA / DRB (format conversion for external eval)

```bash
# Generate + convert to ASTA format
python -m evals.run run --benchmark sqa --data-path path/to/sqa_test.jsonl --num-examples 10

# Generate + convert to DRB format
python -m evals.run run --benchmark drb --data-path path/to/drb_queries.jsonl --num-examples 10
```

Then run external evaluators on the output files in `evals/results/`.

## Options

```
--benchmark, -b    researchqa | healthbench | sqa | drb
--num-examples, -n Number of examples (default: all)
--model, -m        Claude model (default: claude-sonnet-4-20250514)
--max-turns        Max tool-use turns (default: 15)
--threads          Parallel threads (default: 10)
--grader-model     Grading LLM (default: gpt-4.1-mini)
--subset           HealthBench subset: all | hard | consensus
--data-path        Dataset file path (required for sqa/drb)
--output-dir       Results directory (default: evals/results/)
```

## Architecture

```
evals/
├── run.py          # CLI entry point (generate / evaluate / run)
├── types.py        # SamplerResponse, SingleEvalResult, EvalResult
├── sampler.py      # AnthropicToolSampler — Claude API + tool execution loop
├── tools.py        # Tool schemas + subprocess dispatch to paper/paper-search
├── graders.py      # LLM grading (coverage + rubric scoring)
├── common.py       # Parallel map, checkpointing, aggregation
└── benchmarks/
    ├── base.py         # Abstract Eval class
    ├── researchqa.py   # ResearchQA loader + coverage eval
    ├── healthbench.py  # HealthBench loader + rubric eval
    ├── sqa.py          # SQAv2 loader + ASTA format converter
    └── drb.py          # DRB loader + RACE/FACT format converter
```

The sampler runs an agentic loop: send prompt to Claude → Claude requests tool calls → execute CLI commands via subprocess → return results → repeat until final answer or max turns.
