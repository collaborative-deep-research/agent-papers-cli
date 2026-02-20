# agent-papers-cli — Claude Code Demo (Act 2)
# Run: vhs demo/claude-code-demo.tape
# Output: demo/clips/claude-code.mp4
#
# Based on real session afd54b40 — deep research on test-time training.
# Shows the agent autonomously calling paper/paper-search tools.
# For the final video, replace with a real Claude Code recording.

# --- Settings ---
Output demo/clips/claude-code.mp4
Set FontSize 14
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set Padding 20
Set Framerate 30

# Run the simulation
Type "bash demo/simulate-claude-code.sh"
Enter
Sleep 30s
