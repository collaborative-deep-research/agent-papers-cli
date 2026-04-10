"""DR-Tulu compatible prompt templates for citation-aware eval output.

These prompts are appended to the system prompt (via ``--append-system-prompt``)
to instruct Claude to produce ``<cite>`` tagged output that aligns with
DR-Tulu's scoring pipeline (RACE/FACT for DRB, ASTA for SQA, coverage for
ResearchQA).

The existing skill (e.g., ``/deep-research``) still drives the research
workflow.  These prompts *add* citation formatting instructions on top.
"""

# ---------------------------------------------------------------------------
# Citation format instructions (shared across all variants)
# ---------------------------------------------------------------------------

_CITE_FORMAT = """\
## Citation Format

Support every non-trivial claim with retrieved evidence.  When you find
information from search results, paper content, or browsed web pages, wrap
the exact claim span in a ``<cite>`` tag whose ``id`` is the reference
identifier from the tool output.

Reference identifiers appear in tool output as bracketed IDs such as
``[ddd5f455]``, ``[a3b2c1d0]``, ``[r1]``, etc.  These are deterministic
hashes derived from the source URL, so the same source always produces the
same ID across searches.

Use these IDs (without brackets) in your ``<cite>`` tags:

    <cite id="ddd5f455">The transformer architecture was introduced in 2017.</cite>

If multiple sources support a claim, use comma-separated IDs:

    <cite id="ddd5f455,a3b2c1d0">Attention mechanisms allow variable-length context.</cite>

Rules:
- Use **only** reference IDs that appeared in actual tool outputs.
- **Never invent** citation IDs.
- Cite the factual claim, not filler text.
- Each claim should be wrapped individually (don't cite entire paragraphs).
"""

# ---------------------------------------------------------------------------
# Answer wrapper instructions
# ---------------------------------------------------------------------------

_ANSWER_WRAPPER = """\
## Answer Format

Wrap your **final answer** in ``<answer></answer>`` tags.  Everything before
the ``<answer>`` tag is treated as scratch/search work; everything inside is
the deliverable.

Example:

<answer>
## Overview

<cite id="a3b2c1d0">Large language models often hallucinate on long-tail facts.</cite>
Recent work on retrieval-augmented generation addresses this by grounding
responses in <cite id="ddd5f455,e4f5a6b7">retrieved evidence from search engines and
knowledge bases.</cite>

## Key Findings
...
</answer>
"""

# ---------------------------------------------------------------------------
# Prompt variants (matching DR-Tulu's additional_instructions)
# ---------------------------------------------------------------------------

LONG_FORM = _CITE_FORMAT + _ANSWER_WRAPPER + """\
## Response Style — Long Form

Write a comprehensive, evidence-backed answer.  Ground every nontrivial
claim in retrieved evidence using ``<cite id="...">...</cite>`` tags.
Prefer authoritative sources (peer-reviewed papers, reputable benchmarks)
and prioritize recent work for fast-moving areas.  Acknowledge uncertainty
and conflicts; if evidence is thin or sources disagree, state it and
explain what additional evidence would resolve it.

Structure with clear **markdown headers** and a coherent flow.  In each
section, write 2–5 sentence paragraphs with clear topic sentences and
transitions; use lists sparingly.  Synthesize rather than enumerate: group
findings across sources, explain relationships, and build a coherent
narrative.  **DO NOT** invent citations or fabricate content.
"""

SHORT_FORM = _CITE_FORMAT + _ANSWER_WRAPPER + """\
## Response Style — Short Form

Search iteratively to find the answer from multiple sources.  After finding
enough evidence, synthesize it into a short paragraph with citations for
each claim using ``<cite id="...">...</cite>`` tags.  Never fabricate
information.  Put the answer in ``<answer>...</answer>`` tags.
"""

EXACT_ANSWER = _CITE_FORMAT + """\
## Response Style — Exact Answer

Search iteratively to find the answer.  Provide the final answer in the
following format:

    <answer>\\boxed{exact answer}</answer>
"""

# Convenience mapping used by run.py --cite-style flag.
PROMPT_STYLES: dict[str, str] = {
    "long": LONG_FORM,
    "short": SHORT_FORM,
    "exact": EXACT_ANSWER,
}

# Default style per benchmark.
BENCHMARK_CITE_STYLES: dict[str, str] = {
    "researchqa": "long",
    "healthbench": "long",
    "sqa": "long",
    "drb": "long",
}
