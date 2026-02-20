# Evaluation Harness

Evaluate Claude Code's ability to use the `paper` and `paper-search` CLI tools on academic research benchmarks.

The harness spawns `claude -p` (Claude Code in print mode) for each benchmark question. Claude Code loads the project's CLAUDE.md, uses Bash to call `paper`/`paper-search` commands, and returns a researched answer. Grading uses LLM-based scoring via OpenAI.

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

# Required
export OPENAI_API_KEY=...      # For grading (gpt-4.1-mini)

# Claude Code must be installed and authenticated
claude --version
```

Make sure `paper` and `paper-search` are installed and on your PATH.

## Usage

### End-to-end (generate + evaluate)

```bash
python -m evals.run run --benchmark researchqa --num-examples 5
python -m evals.run run --benchmark healthbench --subset hard --num-examples 5
```

### With a specific skill

```bash
python -m evals.run run --benchmark researchqa --num-examples 5 --skill deep-research
python -m evals.run run --benchmark healthbench --num-examples 5 --skill research-coordinator
```

### Generate only

```bash
python -m evals.run generate --benchmark researchqa --num-examples 10 --model sonnet
```

### Evaluate existing generations

```bash
python -m evals.run evaluate --benchmark researchqa --generation-file evals/results/researchqa_gen.jsonl
```

### SQA / DRB (format conversion for external eval)

```bash
python -m evals.run run --benchmark sqa --data-path path/to/sqa_test.jsonl --num-examples 10
python -m evals.run run --benchmark drb --data-path path/to/drb_queries.jsonl --num-examples 10
```

Then run external evaluators on the output files in `evals/results/`.

## Options

```
--benchmark, -b    researchqa | healthbench | sqa | drb
--num-examples, -n Number of examples (default: all)
--model, -m        Claude model alias or full name (default: sonnet)
--max-turns        Max agentic turns per example (default: 15)
--max-budget-usd   Max dollar spend per example
--skill, -s        Skill to use: deep-research | literature-review | fact-check | research-coordinator
--threads          Parallel threads for grading (default: 10)
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
├── sampler.py      # ClaudeCodeSampler — spawns `claude -p` subprocess
├── tools.py        # Reference docs for paper/paper-search CLI commands
├── graders.py      # LLM grading (coverage + rubric scoring via OpenAI)
├── common.py       # Parallel map, checkpointing, aggregation
└── benchmarks/
    ├── base.py         # Abstract Eval class
    ├── researchqa.py   # ResearchQA loader + coverage eval
    ├── healthbench.py  # HealthBench loader + rubric eval
    ├── sqa.py          # SQAv2 loader + ASTA format converter
    └── drb.py          # DRB loader + RACE/FACT format converter
```

### How it works

1. For each benchmark question, the harness calls `claude -p "<question>" --output-format json`
2. Claude Code runs in the project directory, loads CLAUDE.md, and uses Bash to call `paper`/`paper-search`
3. The JSON result contains the final answer, cost, turns, and session metadata
4. The grader (gpt-4.1-mini) scores the answer against the benchmark rubric
5. Results are aggregated and saved to `evals/results/`

### Skills

Pass `--skill <name>` to use a skill as the `--append-system-prompt`. The skill's SKILL.md content is injected, which gives Claude structured research workflows:

- **deep-research**: Broad discovery → narrow → deep read → citation graph → synthesize
- **literature-review**: Multi-query search → triage → deep analysis → themed report
- **fact-check**: Decompose claim → search evidence → verify sources → verdict
- **research-coordinator**: Analyze request → dispatch to appropriate workflow
