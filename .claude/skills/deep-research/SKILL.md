---
name: deep-research
description: Research a topic in depth using web search, academic papers, and citation graphs. Use when the user asks to research, investigate, or explore a topic thoroughly.
argument-hint: [topic or question]
allowed-tools: Bash, Read, Glob, Grep, Write
---

Research "$ARGUMENTS" in depth using the `paper` and `search` CLI tools. Follow this workflow:

## 1. Broad Discovery

Start with broad searches to map the landscape:
```
search google web "$ARGUMENTS"
search semanticscholar papers "$ARGUMENTS" --limit 10
```

Scan titles, snippets, and citation counts. Identify the most relevant papers and key terms.

## 2. Narrow and Filter

Refine based on what you found:
```
search semanticscholar papers "<refined query>" --year 2023-2025 --min-citations 10
search semanticscholar snippets "<specific question>"
search pubmed "<query>"   # if biomedical
```

## 3. Deep Read

For the most relevant papers (at least 3-5), read in depth:
```
paper outline <arxiv_id>           # understand structure first
paper skim <arxiv_id> --lines 3    # quick overview
paper read <arxiv_id> <section>    # read key sections
```

For web sources:
```
search browse <url>
```

## 4. Follow the Citation Graph

For key papers, explore their context:
```
search semanticscholar citations <paper_id> --limit 10    # who cites this?
search semanticscholar references <paper_id> --limit 10   # what does it build on?
search semanticscholar details <paper_id>                  # full metadata
```

## 5. Synthesize

Combine findings into a structured report with:
- Key findings and themes
- Areas of agreement/disagreement
- Gaps in the literature
- Citations for all claims (include paper titles and URLs)

## Guidelines

- Always start broad, then narrow. Don't read deeply until you've scanned widely.
- Read at least 3-5 primary sources before synthesizing.
- Cross-reference web sources against academic papers when possible.
- Use `search semanticscholar snippets` to find specific evidence for claims.
- Track what you've already searched/read to avoid redundancy.
- If a search returns arxiv papers, use `paper read` to get the full text rather than just the snippet.
