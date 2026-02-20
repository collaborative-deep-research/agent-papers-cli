# agent-papers-cli — Full Demo Video (CLI features)
# Run: vhs demo/full-demo.tape
# Output: demo/clips/cli-features.mp4
#
# This generates the Act 1 clip for the Remotion composition.
# Act 2 (Claude Code) should be a real screen recording.

# --- Settings ---
Output demo/clips/cli-features.mp4
Set FontSize 14
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set Padding 20
Set Framerate 30

# ============================================================
# Scene 1: "Navigate a paper"
# Show: outline → skim → read section
# ============================================================

# Show the paper's structure
Type "paper outline 2302.13971"
Enter
Sleep 4s

# Quick skim — headings + first sentence
Type "paper skim 2302.13971 --lines 1"
Enter
Sleep 4s

# Deep dive into a section (note: header auto-suppressed)
Type "paper read 2302.13971 'Architecture'"
Enter
Sleep 4s

# ============================================================
# Scene 2: "Search and discover"
# Show: keyword search → follow citation → follow link
# ============================================================

# Keyword search with highlighted matches
Type "paper search 2302.13971 'attention'"
Enter
Sleep 3.5s

# Follow a citation to the bibliography
Type "paper goto 2302.13971 c3"
Enter
Sleep 3.5s

# Follow an external link
Type "paper goto 2302.13971 e1"
Enter
Sleep 3s

# ============================================================
# Scene 3: "Search the literature"
# Show: google scholar → semantic scholar → browse
# ============================================================

# Google Scholar search
Type "paper-search google scholar 'LLaMA open efficient foundation models'"
Enter
Sleep 4s

# Semantic Scholar — deeper academic search
Type "paper-search semanticscholar papers 'rotary position embeddings' --year 2021-2025 --sort citationCount:desc"
Enter
Sleep 4s

# Get details on a result
Type "paper-search semanticscholar details 204e3073870fae3d05bcbc2f6a8e840b"
Enter
Sleep 3.5s

# ============================================================
# Scene 4: "Detect figures and tables"
# Show: detect → figures → goto figure
# ============================================================

Type "paper figures 2302.13971"
Enter
Sleep 3.5s

Type "paper goto 2302.13971 f1"
Enter
Sleep 3s

# ============================================================
# Scene 5: "Highlight and annotate"
# Show: highlight search → highlight add
# ============================================================

Type "paper highlight search 2302.13971 'pre-normalization'"
Enter
Sleep 3s

Type "paper highlight add 2302.13971 'pre-normalization' --color green --note 'key technique'"
Enter
Sleep 3s
