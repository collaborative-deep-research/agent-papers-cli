# Evaluation Harness

Evaluate Claude Code's ability to use `paper` and `paper-search` CLI tools on academic research benchmarks.

Each benchmark question is sent to `claude -p` with a skill prefix (e.g. `/deep-research <question>`). Claude Code loads CLAUDE.md, uses Bash to call the CLI tools, and returns a researched answer. Grading uses LLM-based scoring via OpenAI.

## Benchmarks

| Benchmark | Default skill | Grading |
|-----------|--------------|---------|
| **ResearchQA** | `/deep-research` | LLM coverage scoring (5-point scale) |
| **HealthBench** | `/deep-research` | LLM rubric scoring (criterion-met) |
| **SQAv2** | `/deep-research` | External ASTA evaluator |
| **DRB** | `/deep-research` | External RACE/FACT scoring |

## Setup

```bash
cd evals && uv pip install .
export OPENAI_API_KEY=...   # for grading (gpt-4.1-mini)
```

`paper`, `paper-search`, and `claude` must be installed and on PATH.

## Usage

```bash
# End-to-end
python -m evals.run run -b researchqa -n 5
python -m evals.run run -b healthbench --subset hard -n 5

# Override skill
python -m evals.run run -b researchqa -n 5 --skill research-coordinator

# No skill (raw prompt)
python -m evals.run run -b researchqa -n 5 --skill ''

# Generate only, then evaluate separately
python -m evals.run generate -b researchqa -n 10
python -m evals.run evaluate -b researchqa -g evals/results/researchqa_gen.jsonl

# SQA/DRB (format conversion for external eval)
python -m evals.run run -b sqa --data-path path/to/sqa.jsonl -n 10
python -m evals.run run -b drb --data-path path/to/drb.jsonl -n 10
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-b, --benchmark` | (required) | `researchqa`, `healthbench`, `sqa`, `drb` |
| `-n, --num-examples` | all | Number of examples |
| `-m, --model` | `sonnet` | Claude model alias or full name |
| `-s, --skill` | per-benchmark | Skill slash command (`''` to disable) |
| `--max-turns` | 15 | Max agentic turns per example |
| `--max-budget-usd` | none | Cost cap per example |
| `--grader-model` | `gpt-4.1-mini` | Grading LLM |
| `--subset` | `all` | HealthBench: `all`, `hard`, `consensus` |
| `--data-path` | none | Dataset path (required for sqa/drb) |

## Architecture

```
evals/
├── run.py           CLI entry point
├── claude.py         run_claude() — spawns `claude -p`, returns dict
├── types.py          SingleEvalResult, EvalResult
├── common.py         map_with_progress, aggregate_results
├── graders.py        LLM grading (coverage + rubric)
├── tools.py          Reference docs for CLI commands
└── benchmarks/
    ├── base.py       Abstract Eval class
    ├── researchqa.py
    ├── healthbench.py
    ├── sqa.py
    └── drb.py
```

### How it works

1. Benchmark formats the question as `/deep-research <question>` (or another skill)
2. `run_claude()` calls `claude -p "<prompt>" --output-format json`
3. Claude Code runs in the project dir, loads CLAUDE.md, uses Bash for paper/paper-search
4. JSON result gives us the answer text + metadata (turns, cost, session_id)
5. Grader (gpt-4.1-mini) scores the answer against the benchmark rubric
