#!/usr/bin/env bash
# Simulates Claude Code agent output for the demo GIF.
# Called from readme.tape to show a sneak peek of agent usage.

CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}╭─────────────────────────────────────────────────────────╮${RESET}"
echo -e "${BOLD}│${RESET}  ${CYAN}claude${RESET}                                                 ${BOLD}│${RESET}"
echo -e "${BOLD}╰─────────────────────────────────────────────────────────╯${RESET}"
echo ""
sleep 0.8

echo -e "${BOLD}> Research the key architectural innovations in LLaMA${RESET}"
echo ""
sleep 1.2

echo -e "${DIM}● Reading paper 2302.13971...${RESET}"
sleep 0.6

echo ""
echo -e "${DIM}$ paper outline 2302.13971${RESET}"
sleep 0.4
echo -e "  Outline"
echo -e "  ├── Abstract [ref=s1]"
echo -e "  ├── 1 Introduction [ref=s2]"
echo -e "  ├── 2 Approach [ref=s3]"
echo -e "  │   ├── 2.1 Pre-training Data [ref=s4]"
echo -e "  │   ├── ${YELLOW}2.2 Architecture${RESET} [ref=s5]"
echo -e "  │   ├── 2.3 Optimizer [ref=s6]"
echo -e "  │   └── 2.4 Efficient implementation [ref=s7]"
echo -e "  ├── 3 Main results [ref=s8]"
echo -e "  ${DIM}...${RESET}"
sleep 1.5

echo ""
echo -e "${DIM}$ paper read 2302.13971 'Architecture'${RESET}"
sleep 0.4
echo -e "  ${BOLD}2.2 Architecture${RESET}"
echo -e "  Our network is based on the transformer architecture"
echo -e "  (Vaswani et al., 2017). We leverage various improvements"
echo -e "  that were subsequently proposed..."
echo -e "  ${DIM}Showing 50 of 84 sentences.${RESET}"
sleep 1.5

echo ""
echo -e "${DIM}$ paper-search semanticscholar papers 'RMSNorm pre-normalization'${RESET}"
sleep 0.4
echo -e "  ${GREEN}[1]${RESET} Root Mean Square Layer Normalization (Zhang & Sennrich, 2019)"
echo -e "  ${GREEN}[2]${RESET} On Layer Normalization in the Transformer Architecture (Xiong et al., 2020)"
echo -e "  ${DIM}...${RESET}"
sleep 1.5

echo ""
echo -e "${DIM}● Synthesizing findings...${RESET}"
sleep 2
