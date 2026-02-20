# agent-papers-cli — Full Demo Video (CLI features)
# Run: vhs demo/full-demo.tape
# Output: demo/clips/cli-features.mp4
#
# This generates the Act 1 clip for the Remotion composition.
# ~30 seconds: 3 scenes showcasing core features.

# --- Settings ---
Output demo/clips/cli-features.mp4
Set FontSize 18
Set Width 1920
Set Height 1080
Set Theme "nord-light"
Set TypingSpeed 35ms
Set Padding 20
Set Framerate 30

# Let the terminal settle before typing
Sleep 1.5s

# ============================================================
# Scene 1: "Navigate a paper"
# Show: outline → read a section
# ============================================================

Type "paper outline 2302.13971"
Sleep 0.3s
Enter
Sleep 4s

# Header auto-suppressed on consecutive call
Type "paper read 2302.13971 'Architecture'"
Sleep 0.3s
Enter
Sleep 5s

# ============================================================
# Scene 2: "Search within a paper"
# Show: keyword search → follow a citation
# ============================================================

Type "paper search 2302.13971 'attention'"
Sleep 0.3s
Enter
Sleep 4s

Type "paper goto 2302.13971 c3"
Sleep 0.3s
Enter
Sleep 3s

# ============================================================
# Scene 3: "Search the literature"
# Show: semantic scholar → google scholar
# ============================================================

Type "paper-search semanticscholar papers 'rotary position embeddings' --year 2021-2025"
Sleep 0.3s
Enter
Sleep 4.5s

Type "paper-search google scholar 'LLaMA open efficient foundation models'"
Sleep 0.3s
Enter
Sleep 4.5s
