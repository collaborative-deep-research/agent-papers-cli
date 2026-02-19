# Agent Skills for Deep Research

This repo includes Claude Code skills for agent-driven research workflows. Each skill is a slash command that can be invoked directly.

## Available Skills

| Skill | Command | Description |
|-------|---------|-------------|
| [Research Coordinator](.claude/skills/research-coordinator/SKILL.md) | `/research-coordinator` | Top-level coordinator that analyzes your request and picks the right workflow |
| [Deep Research](.claude/skills/deep-research/SKILL.md) | `/deep-research` | Broad-to-deep investigation of a topic |
| [Literature Review](.claude/skills/literature-review/SKILL.md) | `/literature-review` | Systematic survey of academic literature |
| [Fact Check](.claude/skills/fact-check/SKILL.md) | `/fact-check` | Verify claims against web and academic sources |

## Usage

```bash
# Let the coordinator decide the approach
/research-coordinator what are the main approaches to RLHF?

# Or invoke a specific workflow directly
/deep-research retrieval augmented generation for medical QA
/literature-review transformer efficiency methods 2022-2025
/fact-check GPT-4 was trained on 13 trillion tokens
```

## Required Tools

These skills use the `paper` and `paper-search` CLI tools. Install with:

```bash
uv pip install -e .
```

### API Keys

Run `paper-search env` to check which keys are configured. Save keys persistently with:
```
paper-search env set SERPER_API_KEY <key>   # required for paper-search google, paper-search browse --backend serper
paper-search env set S2_API_KEY <key>       # optional, recommended for paper-search semanticscholar (higher rate limits)
paper-search env set JINA_API_KEY <key>     # required for paper-search browse --backend jina
```
Keys are stored in `~/.papers/.env` and loaded automatically.

## Command Reference

### `paper` — Read academic papers
```
paper outline <ref>                    # Show heading tree
paper read <ref> [section]             # Read full paper or specific section
paper skim <ref> --lines N --level L   # Headings + first N sentences
paper search <ref> "query"             # Keyword search within a paper
paper info <ref>                       # Show metadata
paper goto <ref> <ref_id>              # Jump to ref (s3, e1, c5)
```
`<ref>` accepts: `2302.13971`, `arxiv.org/abs/2302.13971`, `arxiv.org/pdf/2302.13971`

### `paper-search` — Search the web and literature
```
paper-search env                             # Check API key status
paper-search env set KEY value               # Save a key to ~/.papers/.env

paper-search google web "query"              # Google web search (Serper)
paper-search google scholar "query"          # Google Scholar search (Serper)

paper-search semanticscholar papers "query"  # Academic paper search
  [--year 2023-2025] [--min-citations 10] [--venue ACL] [--sort citationCount:desc] [--limit N]
paper-search semanticscholar snippets "query"  # Text snippet search
  [--year 2024] [--paper-ids id1,id2]
paper-search semanticscholar citations <id>  # Papers citing this one
paper-search semanticscholar references <id> # Papers this one references
paper-search semanticscholar details <id>    # Full paper metadata

paper-search pubmed "query"                  # PubMed biomedical search
  [--limit N] [--offset N]

paper-search browse <url>                    # Extract webpage content
  [--backend jina|serper] [--timeout 30]
```
