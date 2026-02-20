#!/usr/bin/env bash
# Simulates a Claude Code deep-research session.
# Based on real session afd54b40 — researching test-time training.
#
# For the final video, replace with a real screen recording.
# This script produces the "ideal" pacing for the demo.

CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
WHITE='\033[1;37m'
MAGENTA='\033[0;35m'
RED='\033[0;31m'
BLUE='\033[0;34m'
RESET='\033[0m'

# Helper: print a tool call line
tool() { echo -e "  ${MAGENTA}▸${RESET} ${DIM}$1${RESET}"; }
# Helper: dim text
dim() { echo -e "  ${DIM}$1${RESET}"; }
# Helper: agent narration
narrate() { echo -e "  $1"; echo ""; }

# ── Claude Code splash ──
echo ""
echo -e "  ${MAGENTA}  ✻${RESET}"
echo -e "  ${MAGENTA}  |${RESET}"
echo -e "  ${MAGENTA} ▟█▙${RESET}     ${BOLD}Claude Code${RESET} v2.1.49"
echo -e "  ${MAGENTA}▐▛███▜▌${RESET}   ${DIM}Opus 4.6 · Unlimited usage${RESET}"
echo -e "  ${MAGENTA}▝▜█████▛▘${RESET}  ${DIM}~/agent-papers-cli${RESET}"
echo -e "  ${MAGENTA} ▘▘ ▝▝${RESET}"
echo ""
sleep 1.2

# ── User prompt ──
echo -e "${BOLD}${WHITE}>${RESET} ${BOLD}/deep-research find me papers about test time training${RESET}"
echo ""
sleep 1.2

# ── Phase 1: Broad Discovery ──
narrate "I'll research ${BOLD}test-time training${RESET} for you. Let me start with broad discovery."
sleep 0.8

tool "paper-search google web \"test time training machine learning\""
echo ""
sleep 0.3
dim "  [r1] Test-Time Training with Self-Supervision — Yu Sun et al."
dim "  [r2] TTT: Learning to Compress — Yu Sun et al., 2024"
dim "  [r3] Test-Time Training Done Right — Shao et al., 2025"
dim "  ..."
echo ""
sleep 1.2

tool "paper-search semanticscholar papers \"test time training\" --limit 10"
echo ""
sleep 0.3
echo -e "    ${GREEN}[s1]${RESET} Test-Time Training with Self-Supervision (Sun et al., 2020)"
echo -e "        ${DIM}Cited by: 847${RESET}"
echo -e "    ${GREEN}[s2]${RESET} Learning to (Learn at Test Time): RNNs with Expressive Hidden States (2024)"
echo -e "        ${DIM}Cited by: 203 · arXiv:2407.04620${RESET}"
echo -e "    ${GREEN}[s3]${RESET} TTT Done Right: LaCT (Shao et al., 2025)"
echo -e "        ${DIM}Cited by: 34 · arXiv:2505.23884${RESET}"
echo ""
sleep 1.5

# ── Phase 2: Deep Read ──
narrate "Good landscape. Let me deep-read the key papers."
sleep 0.6

tool "paper outline 2407.04620"
echo ""
sleep 0.3
echo -e "    Outline"
echo -e "    ├── Abstract"
echo -e "    ├── Introduction"
echo -e "    ├── ${YELLOW}Method${RESET} [ref=s3]"
echo -e "    │   ├── TTT as updating a hidden state [ref=s4]"
echo -e "    │   └── TTT layers [ref=s5]"
echo -e "    ├── Experiments"
echo -e "    ${DIM}...${RESET}"
echo ""
sleep 1

tool "paper read 2407.04620 'Method'"
echo ""
sleep 0.3
echo -e "    ${BOLD}Method${RESET}"
echo -e "    Self-supervised learning happens not just during training"
echo -e "    but also at test time. Each test input is used to update"
echo -e "    model parameters before making a prediction. We replace"
echo -e "    the hidden state of an RNN with a model being updated"
echo -e "    by self-supervised learning on the test sequence..."
echo -e "    ${DIM}Showing 50 of 127 sentences.${RESET}"
echo ""
sleep 1.5

# ── Phase 3: Citation Graph ──
narrate "Let me follow the citation graph to understand the lineage."
sleep 0.6

tool "paper-search semanticscholar citations 35ab93f41115e860 --limit 10"
echo ""
sleep 0.3
echo -e "    ${GREEN}[1]${RESET} E2E TTT: End-to-End Test Time Training (2024)"
echo -e "        ${DIM}arXiv:2512.23675${RESET}"
echo -e "    ${GREEN}[2]${RESET} TTT Done Right (Shao et al., 2025)"
echo -e "        ${DIM}arXiv:2505.23884${RESET}"
echo -e "    ${GREEN}[3]${RESET} One-Minute Video Generation with TTT (2025)"
echo -e "        ${DIM}arXiv:2504.05298${RESET}"
echo ""
sleep 1.5

tool "paper read 2505.23884 'Introduction'"
echo ""
sleep 0.3
echo -e "    ${BOLD}Introduction${RESET}"
echo -e "    TTT layers replace the linear attention in Mamba-like"
echo -e "    architectures with a learned self-supervised objective."
echo -e "    We show that prior TTT layers were underfitting and"
echo -e "    propose LaCT (Large-Chunk TTT) to fix this..."
echo -e "    ${DIM}Showing 50 of 96 sentences.${RESET}"
echo ""
sleep 1.5

# ── Phase 4: Synthesis ──
narrate "${DIM}● Synthesizing findings across 4 papers...${RESET}"
sleep 1.5

echo -e "  ${BOLD}${WHITE}## Test-Time Training: Research Landscape${RESET}"
echo ""
echo -e "  ${BOLD}1. Foundation (Sun et al., 2020)${RESET}"
echo -e "     Self-supervised learning at test time — each input"
echo -e "     updates model parameters before prediction."
echo ""
echo -e "  ${BOLD}2. TTT Layers (Sun et al., 2024)${RESET}"
echo -e "     Replace RNN hidden state with a model updated by"
echo -e "     self-supervised learning. Linear complexity, expressive"
echo -e "     hidden state."
echo ""
echo -e "  ${BOLD}3. TTT Done Right / LaCT (Shao et al., 2025)${RESET}"
echo -e "     Prior TTT layers were underfitting. Large-chunk TTT"
echo -e "     + non-linear fast-weight updates close the gap with"
echo -e "     Transformers."
echo ""
echo -e "  ${BOLD}4. Applications${RESET}"
echo -e "     Long-context language modeling, video generation,"
echo -e "     abstract reasoning (ARC challenge)."
echo ""
sleep 3
