# Demo Video Plan

## File overview

```
demo/
├── PLAN.md                    # This file
├── readme.tape                # VHS script → readme.gif (short, for README)
├── readme.gif                 # Generated README GIF
├── full-demo.tape             # VHS script → clips/cli-features.mp4
├── claude-code-demo.tape      # VHS script → clips/claude-code.mp4
├── simulate-agent.sh          # Short agent simulation (for readme GIF)
├── simulate-claude-code.sh    # Full agent simulation (for Act 2)
└── clips/                     # VHS-generated MP4 clips (gitignored)
    ├── cli-features.mp4
    └── claude-code.mp4
```

## Pipeline

```
VHS .tape scripts
    ↓ (vhs <file>.tape)
MP4 clips in demo/clips/
    ↓ (import as <Video> components)
Remotion composition
    ↓ (npx remotion render)
Final MP4 + README GIF
```

## Storyline

The video has a clear narrative arc: **"Here are the tools → Watch your agent use them"**

### Act 1: CLI Features (~60-90 sec)

Five scenes, each demonstrating a capability:

| Scene | What it shows | Commands | Connection to Act 2 |
|-------|--------------|----------|---------------------|
| 1. Navigate | Paper structure | `outline`, `skim`, `read "Architecture"` | Agent will outline → read to understand a paper |
| 2. Search & discover | Finding content | `search "attention"`, `goto c3`, `goto e1` | Agent will search + follow citations |
| 3. Literature search | Finding papers | `google scholar`, `semanticscholar papers`, `details` | Agent will search for related work |
| 4. Layout detection | Figures & tables | `figures`, `goto f1` | Agent can inspect visual elements |
| 5. Highlights | Annotate | `highlight search`, `highlight add` | Agent can mark important findings |

### Transition

Title card: *"Now let your agent do it."*

### Act 2: Claude Code (~60-90 sec)

Based on real session `afd54b40` — deep research on test-time training.

**Prompt:** `/deep-research find me papers about test time training`

The agent autonomously:
1. **Broad discovery** — `paper-search google web` + `semanticscholar papers` (Scene 3 callback)
2. **Deep read** — `paper outline` + `paper read "Method"` (Scene 1 callback)
3. **Citation graph** — `semanticscholar citations` + reads citing papers (Scene 2 callback)
4. **Synthesizes** a structured report across 4 papers

Each tool call mirrors a scene from Act 1 — the viewer recognizes the same commands now being orchestrated by the agent. The real session had ~30 tool calls with self-corrections — we show the clean version for the demo.

### Outro

- GitHub URL + `pip install agent-papers-cli`
- `npx skills add collaborative-deep-research/agent-papers-cli`

## Remotion structure

```
demo/remotion/
├── package.json
├── remotion.config.ts
└── src/
    ├── Root.tsx                # Main composition
    ├── scenes/
    │   ├── Intro.tsx           # Title card + tagline
    │   ├── CliFeatures.tsx     # Act 1 — wraps cli-features.mp4
    │   ├── Transition.tsx      # "Now let your agent do it."
    │   ├── ClaudeCode.tsx      # Act 2 — wraps claude-code.mp4
    │   └── Outro.tsx           # GitHub link, install command
    ├── components/
    │   ├── Callout.tsx         # Annotation overlay (e.g., "↑ header auto-suppressed")
    │   └── SceneLabel.tsx      # Scene title (e.g., "Navigate a paper")
    └── assets/
        └── clips/              # Symlink to ../clips/
```

## Generating clips

```bash
# Part 1: CLI features
vhs demo/full-demo.tape

# Part 2: Claude Code simulation
vhs demo/claude-code-demo.tape

# Or for the README GIF only:
vhs demo/readme.tape
```

## TODO

- [ ] Replace `simulate-claude-code.sh` with a real Claude Code screen recording
- [ ] Set up Remotion project in `demo/remotion/`
- [ ] Add scene label overlays in Remotion
- [ ] Add callout annotations (e.g., "header auto-suppressed", "following citation")
- [ ] Render final video
- [ ] Embed README GIF in README.md
