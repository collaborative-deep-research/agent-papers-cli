"""Reference listing of paper/paper-search CLI commands.

When using the ClaudeCodeSampler, Claude Code has direct access to these
tools via Bash.  This module exists purely as documentation — the sampler
does not import anything from here.

Paper tools
-----------
paper outline <ref>                      Show heading tree
paper read <ref> [section]               Read full paper or a specific section
paper skim <ref> [--lines N] [--level L] Headings + first N sentences
paper search <ref> "query"               Keyword search within a paper
paper info <ref>                         Show metadata (sections, pages, etc.)
paper goto <ref> <ref_id>                Jump to ref (s3, c5, f1, t2, eq3)

Search tools
------------
paper-search google web "query"                Google web search (Serper)
paper-search google scholar "query"            Google Scholar search (Serper)
paper-search semanticscholar papers "query"    Semantic Scholar paper search
paper-search semanticscholar snippets "query"  Text snippet search
paper-search semanticscholar citations <id>    Papers citing this one
paper-search semanticscholar references <id>   Papers referenced by this one
paper-search semanticscholar details <id>      Full paper metadata
paper-search pubmed "query" [--limit N]        PubMed biomedical search
paper-search browse <url>                      Extract webpage content
"""
