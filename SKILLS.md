# Agent Skills for Deep Research

This file describes research workflows for AI agents using the `paper` and `search` CLI tools. Copy the relevant skill into your agent's system prompt or `.claude/skills/` directory.

---

## Skill: Deep Research

When asked to research a topic in depth, follow this workflow:

### 1. Broad Discovery
Start with broad searches to map the landscape:
```
search google web "<topic>"
search semanticscholar papers "<topic>" --limit 10
```

### 2. Narrow and Filter
Refine based on initial results:
```
search semanticscholar papers "<refined query>" --year 2023-2025 --min-citations 10
search semanticscholar snippets "<specific question>"
search pubmed "<query>"   # if biomedical
```

### 3. Deep Read
For the most relevant papers, read in depth:
```
paper outline <arxiv_id>           # understand structure first
paper skim <arxiv_id> --lines 3    # quick overview
paper read <arxiv_id> <section>    # read key sections
```

For web sources:
```
search browse <url>
```

### 4. Follow the Citation Graph
For key papers, explore their context:
```
search semanticscholar citations <paper_id> --limit 10    # who cites this?
search semanticscholar references <paper_id> --limit 10   # what does it build on?
search semanticscholar details <paper_id>                  # full metadata
```

### 5. Synthesize
Combine findings into a structured report with:
- Key findings and themes
- Areas of agreement/disagreement
- Gaps in the literature
- Citations for all claims (include URLs)

### Guidelines
- Always start broad, then narrow. Don't read deeply until you've scanned widely.
- Read at least 3-5 primary sources before synthesizing.
- Cross-reference web sources against academic papers when possible.
- Use `search semanticscholar snippets` to find specific evidence for claims.
- Track what you've already searched/read to avoid redundancy.

---

## Skill: Literature Review

When asked to do a systematic literature review:

### 1. Define Scope
Clarify with the user: topic, year range, target venues, number of papers.

### 2. Multi-Query Search
Search with multiple query variations to maximize coverage:
```
search semanticscholar papers "<main query>" --limit 20 --year <range>
search semanticscholar papers "<synonym query>" --limit 20 --year <range>
search semanticscholar papers "<related query>" --limit 20 --year <range>
```

### 3. Triage
For each unique paper found:
```
search semanticscholar details <paper_id>
paper skim <arxiv_id> --lines 2
```
Categorize as: highly relevant / somewhat relevant / not relevant.

### 4. Deep Analysis
For highly relevant papers:
```
paper outline <arxiv_id>
paper read <arxiv_id> introduction
paper read <arxiv_id> method
paper read <arxiv_id> results
paper read <arxiv_id> conclusion
```

### 5. Citation Graph Exploration
For seminal papers, find related work:
```
search semanticscholar citations <paper_id> --limit 20
search semanticscholar references <paper_id> --limit 20
```

### 6. Produce Report
Organize findings by theme, not by paper. Include:
- Overview of the field
- Key methods and approaches
- Main results and findings
- Open questions and future directions
- Complete reference list

---

## Skill: Fact Check

When asked to verify a claim:

### 1. Decompose
Break the claim into specific, verifiable sub-claims.

### 2. Search for Evidence
For each sub-claim:
```
search google web "<sub-claim as question>"
search semanticscholar snippets "<sub-claim keywords>"
search semanticscholar papers "<sub-claim keywords>" --limit 5
```

### 3. Verify Sources
For each promising source:
```
paper read <arxiv_id> <relevant section>   # for papers
search browse <url>                         # for web pages
```

### 4. Assess
For each sub-claim, report:
- **Supported**: strong evidence from multiple reliable sources
- **Partially supported**: some evidence, with caveats
- **Unsupported**: no evidence found, or evidence contradicts the claim
- **Uncertain**: insufficient evidence to judge

Always cite specific sources with URLs.

---

## Available Commands Reference

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

### `search` — Search the web and literature
```
search google web "query"              # Google web search (Serper)
search google scholar "query"          # Google Scholar search (Serper)

search semanticscholar papers "query"  # Academic paper search
  [--year 2023-2025] [--min-citations 10] [--venue ACL] [--sort citationCount:desc] [--limit N]
search semanticscholar snippets "query"  # Text snippet search
  [--year 2024] [--paper-ids id1,id2]
search semanticscholar citations <id>  # Papers citing this one
search semanticscholar references <id> # Papers this one references
search semanticscholar details <id>    # Full paper metadata

search pubmed "query"                  # PubMed biomedical search
  [--limit N] [--offset N]

search browse <url>                    # Extract webpage content
  [--backend jina|serper] [--timeout 30]
```

### API Keys
Set these environment variables for search backends:
- `SERPER_API_KEY` — required for `search google` commands
- `S2_API_KEY` — optional but recommended for `search semanticscholar` (higher rate limits)
- `JINA_API_KEY` — required for `search browse` with jina backend
