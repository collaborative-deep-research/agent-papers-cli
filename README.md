# paper

A command-line tool for reading, skimming, and searching academic papers.

## Install

```bash
uv pip install -e .
```

## Usage

```bash
paper outline 2301.12345
paper read 2301.12345
paper read 2301.12345 "method"
paper skim 2301.12345 --lines 3
paper search 2301.12345 "transformer"
paper info 2301.12345
```
