# agent-papers-cli — Claude Code Demo (Act 2)
# Run: vhs demo/claude-code-demo.tape
# Output: demo/clips/claude-code.mp4
#
# Based on real session afd54b40 — deep research on test-time training.
# Shows the agent autonomously calling paper/paper-search tools.
# For the final video, replace with a real Claude Code recording.

# --- Settings ---
Output demo/clips/claude-code.mp4
Set FontSize 18
Set Width 1920
Set Height 1080
Set Theme "nord-light"
Set TypingSpeed 35ms
Set Padding 20
Set Framerate 30

# Let the terminal settle before typing
Sleep 1.5s

# Run the simulation
Type "bash demo/run-claude-code.sh"
Sleep 0.3s
Enter
Sleep 30s
