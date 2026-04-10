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
cd evals && pip install -e .
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

## DR-Tulu Compatible Citation Mode

Use `--cite-style` to enable DR-Tulu compatible `<cite>` tags in output.
This appends citation formatting instructions to the system prompt, producing
output that can be scored by DR-Tulu's RACE/FACT and ASTA pipelines.

```bash
# Enable citation mode (benchmark-specific default style)
python -m evals.run run -b drb -n 5 --cite-style auto

# Explicit long-form citation style
python -m evals.run run -b researchqa -n 10 --cite-style long

# Convert existing generation data to DR-Tulu format
python -m evals.run convert -g evals/results/sonnet/deep-research/drb_gen.jsonl
```

With `--cite-style` enabled, the eval harness automatically sets
`PAPER_SEARCH_HASH_IDS=1`, which switches search result reference IDs from
sequential (`[r1]`, `[r2]`) to deterministic hashes (`[ddd5f455]`, `[cfda4fd6]`)
derived from the source URL.  This ensures citation IDs are unique across
multiple searches, so the formatter can trace each
`<cite id="ddd5f455">claim</cite>` back to its source URL.

The hash ID mode can also be enabled manually:

```bash
export PAPER_SEARCH_HASH_IDS=1
paper-search google web "transformers"   # → [ddd5f455] Attention is All You Need
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
| `--cite-style` | none | `auto`, `long`, `short`, `exact` — enables `<cite>` tags |
| `--grader-model` | `gpt-4.1-mini` | Grading LLM |
| `--subset` | `all` | HealthBench: `all`, `hard`, `consensus` |
| `--data-path` | none | Dataset path (auto-downloaded if omitted) |

## Output

Results are saved to `evals/results/` (two files per run):

### `{benchmark}_gen.jsonl` — Generation data

One JSON object per example with the full research trajectory:

```jsonc
{
  "item_id": "174539438139989436-s6",
  "query": "How do pyrolysis temperature and heating rate affect...",
  "field": "Geology",
  "response_text": "## Deep Research Report: ...",
  "rubric": [{"rubric_item": "Does the response specify...", "type": "Other"}, ...],
  "claude": {
    "result": "## Deep Research Report: ...",
    "num_turns": 18,
    "total_cost_usd": 0.157,
    "session_id": "8c4c328a-...",
    "is_error": false,
    "subtype": "success",
    "duration_ms": 119190,
    "usage": { "input_tokens": 59, "output_tokens": 6496, ... },
    "trajectory": [
      {"type": "thinking", "text": "The user is asking me to..."},
      {"type": "text", "text": "I'll conduct a comprehensive..."},
      {"type": "tool_use", "name": "Bash", "input": {"command": "paper-search google web \"pyrolysis...\""}},
      {"type": "tool_result", "content": "Found 10 results from Google\n\n[a3b2c1d0] Effect of..."},
      {"type": "tool_use", "name": "Bash", "input": {"command": "paper-search semanticscholar papers \"biochar...\""}},
      {"type": "tool_result", "content": "Found 10 results from Semantic Scholar\n\n[ddd5f455]..."},
      ...
    ]
  }
}
```

**Trajectory event types:**

| Type | Description |
|------|-------------|
| `thinking` | Claude's internal reasoning (truncated to 1000 chars) |
| `text` | Assistant text output |
| `tool_use` | Tool call with `name` (e.g. `Bash`, `Skill`, `Read`) and `input` |
| `tool_result` | Tool output (truncated to 2000 chars) |

### `{benchmark}_eval.json` — Aggregate scores

```json
{
  "score": 0.85,
  "metrics": {
    "coverage_score": 0.85,
    "coverage_score:std": 0.12
  }
}
```

## Architecture

```
evals/
├── run.py           CLI entry point (generate / evaluate / run / convert)
├── claude.py         run_claude() — spawns `claude -p --output-format stream-json --verbose`
├── prompts.py        DR-Tulu compatible citation prompt templates
├── compat.py         Output format conversion (our format → DR-Tulu format)
├── types.py          SingleEvalResult, EvalResult
├── common.py         map_with_progress, aggregate_results
├── graders.py        LLM grading (coverage + rubric)
├── tools.py          Reference docs for CLI commands
└── benchmarks/
    ├── base.py       Abstract Eval class
    ├── researchqa.py  Coverage scoring
    ├── healthbench.py Rubric scoring
    ├── sqa.py         ASTA format conversion (with snippet content)
    └── drb.py         DRB format conversion (with URL resolution)
```

### How it works

1. Benchmark formats the question as `/deep-research <question>` (or another skill)
2. `run_claude()` calls `claude -p "<prompt>" --output-format stream-json --verbose`
3. Claude Code runs in the project dir, loads CLAUDE.md, uses Bash for paper/paper-search
4. Stream-JSON output is parsed into a structured dict with the final answer text, metadata (turns, cost, session_id), and the full **trajectory** of tool calls and results
5. Grader (gpt-4.1-mini) scores the answer against the benchmark rubric
