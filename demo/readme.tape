# agent-papers-cli — README GIF
# Run: vhs demo/readme.tape
# Output: demo/readme.gif

# --- Settings ---
Output demo/readme.gif
Set FontSize 14
Set Width 1200
Set Height 700
Set Theme "nord-light"
Set TypingSpeed 40ms
Set Padding 20
Set Framerate 24

# ============================================================
# Part 1: "The tools" — quick-fire CLI demo
# ============================================================

# Show the paper's structure
Type "paper outline 2302.13971"
Enter
Sleep 3.5s

# Read a section — header auto-suppressed on same paper
Type "paper read 2302.13971 'abstract'"
Enter
Sleep 3.5s

# Keyword search with highlighted matches
Type "paper search 2302.13971 'transformer'"
Enter
Sleep 3s

# Follow a citation reference
Type "paper goto 2302.13971 c5"
Enter
Sleep 3s

# Search the academic literature
Type "paper-search google scholar 'LLaMA open foundation models'"
Enter
Sleep 3s

# ============================================================
# Part 2: Claude Code sneak peek
# TODO: Replace with a real Claude Code screen recording.
# Record a short session of Claude Code calling paper/paper-search
# commands autonomously, then splice it in via Remotion or
# re-record this tape with a live `claude` invocation.
# ============================================================
