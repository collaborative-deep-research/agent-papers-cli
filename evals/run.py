"""CLI entry point for the eval harness.

Usage:
    python -m evals.run generate --benchmark researchqa --num-examples 10
    python -m evals.run evaluate --benchmark researchqa --generation-file results/researchqa_gen.jsonl
    python -m evals.run run --benchmark healthbench --subset hard --num-examples 5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def _get_benchmark(name: str, args: argparse.Namespace) -> Any:
    """Instantiate a benchmark by name."""
    num = getattr(args, "num_examples", None)
    n_threads = getattr(args, "threads", 10)
    grader = getattr(args, "grader_model", "gpt-4.1-mini")
    output_dir = getattr(args, "output_dir", RESULTS_DIR)

    if name == "researchqa":
        from .benchmarks.researchqa import ResearchQAEval
        return ResearchQAEval(
            data_path=getattr(args, "data_path", None),
            num_examples=num,
            n_threads=n_threads,
            grader_model=grader,
        )
    elif name == "healthbench":
        from .benchmarks.healthbench import HealthBenchEval
        return HealthBenchEval(
            subset=getattr(args, "subset", "all"),
            num_examples=num,
            n_threads=n_threads,
            grader_model=grader,
        )
    elif name == "sqa":
        from .benchmarks.sqa import SQAEval
        data_path = getattr(args, "data_path", None)
        if data_path is None:
            print("Error: --data-path is required for sqa benchmark", file=sys.stderr)
            sys.exit(1)
        return SQAEval(
            data_path=data_path,
            num_examples=num,
            n_threads=n_threads,
            output_dir=output_dir,
        )
    elif name == "drb":
        from .benchmarks.drb import DRBEval
        data_path = getattr(args, "data_path", None)
        if data_path is None:
            print("Error: --data-path is required for drb benchmark", file=sys.stderr)
            sys.exit(1)
        return DRBEval(
            data_path=data_path,
            num_examples=num,
            n_threads=n_threads,
            output_dir=output_dir,
        )
    else:
        print(f"Error: unknown benchmark '{name}'", file=sys.stderr)
        sys.exit(1)


def _build_system_prompt(args: argparse.Namespace) -> str | None:
    """Build a system prompt, optionally prepending a skill."""
    skill = getattr(args, "skill", None)
    if not skill:
        return None  # Use default from ClaudeCodeSampler

    # Load the skill SKILL.md and use it as the system prompt
    skill_path = os.path.join(
        os.path.dirname(__file__), os.pardir,
        ".claude", "skills", skill, "SKILL.md",
    )
    skill_path = os.path.normpath(skill_path)
    if not os.path.exists(skill_path):
        print(f"Error: skill not found: {skill_path}", file=sys.stderr)
        sys.exit(1)

    with open(skill_path) as f:
        content = f.read()

    # Strip YAML front matter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()

    return content


def _make_sampler(args: argparse.Namespace):
    from .sampler import ClaudeCodeSampler

    system_prompt = _build_system_prompt(args)
    kwargs: dict[str, Any] = {
        "model": getattr(args, "model", "sonnet"),
        "max_turns": getattr(args, "max_turns", 15),
    }
    if system_prompt is not None:
        kwargs["system_prompt"] = system_prompt

    budget = getattr(args, "max_budget_usd", None)
    if budget is not None:
        kwargs["max_budget_usd"] = budget

    return ClaudeCodeSampler(**kwargs)


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate responses only."""
    benchmark = _get_benchmark(args.benchmark, args)
    sampler = _make_sampler(args)

    logger.info("Generating with %s on %s", args.model, args.benchmark)
    gen_data = benchmark.generate(sampler)

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"{args.benchmark}_gen.jsonl")
    with open(out_path, "w") as f:
        for row in gen_data:
            f.write(json.dumps(row, default=str) + "\n")
    logger.info("Saved %d generations to %s", len(gen_data), out_path)


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Score an existing generation file."""
    benchmark = _get_benchmark(args.benchmark, args)

    gen_path = args.generation_file
    if not os.path.exists(gen_path):
        print(f"Error: generation file not found: {gen_path}", file=sys.stderr)
        sys.exit(1)

    with open(gen_path) as f:
        gen_data = [json.loads(line) for line in f if line.strip()]

    logger.info("Evaluating %d examples from %s", len(gen_data), gen_path)
    results = benchmark.evaluate(gen_data)

    # Aggregate
    from .common import aggregate_results
    eval_result = aggregate_results(results)

    # Print results
    print(f"\n{'='*60}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Score: {eval_result.score:.4f}" if eval_result.score is not None else "Score: N/A (external eval needed)")
    if eval_result.metrics:
        for k, v in sorted(eval_result.metrics.items()):
            if not k.endswith(":std") and not k.endswith(":bootstrap_std"):
                print(f"  {k}: {v:.4f}")
    print(f"{'='*60}\n")

    # Save detailed results
    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"{args.benchmark}_eval.json")
    with open(out_path, "w") as f:
        json.dump(
            {
                "score": eval_result.score,
                "metrics": eval_result.metrics,
                "n_examples": len(results),
            },
            f,
            indent=2,
            default=str,
        )
    logger.info("Saved eval results to %s", out_path)


def cmd_run(args: argparse.Namespace) -> None:
    """Generate + evaluate end-to-end."""
    benchmark = _get_benchmark(args.benchmark, args)
    sampler = _make_sampler(args)

    logger.info("Running %s end-to-end with %s", args.benchmark, args.model)
    eval_result = benchmark(sampler)

    # Print results
    print(f"\n{'='*60}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Score: {eval_result.score:.4f}" if eval_result.score is not None else "Score: N/A (external eval needed)")
    if eval_result.metrics:
        for k, v in sorted(eval_result.metrics.items()):
            if not k.endswith(":std") and not k.endswith(":bootstrap_std"):
                print(f"  {k}: {v:.4f}")
    print(f"{'='*60}\n")

    # Save full results
    os.makedirs(args.output_dir, exist_ok=True)

    # Save generations
    gen_path = os.path.join(args.output_dir, f"{args.benchmark}_gen.jsonl")
    if eval_result.per_example_results:
        with open(gen_path, "w") as f:
            for row in eval_result.per_example_results:
                f.write(json.dumps(row, default=str) + "\n")

    # Save eval summary
    eval_path = os.path.join(args.output_dir, f"{args.benchmark}_eval.json")
    with open(eval_path, "w") as f:
        json.dump(
            {"score": eval_result.score, "metrics": eval_result.metrics},
            f,
            indent=2,
            default=str,
        )
    logger.info("Saved results to %s", args.output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m evals.run",
        description="Evaluation harness for paper/paper-search CLI tools (uses Claude Code)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--benchmark", "-b", required=True,
        choices=["researchqa", "healthbench", "sqa", "drb"],
        help="Benchmark to run.",
    )
    common.add_argument("--num-examples", "-n", type=int, default=None)
    common.add_argument("--threads", type=int, default=10)
    common.add_argument("--output-dir", default=RESULTS_DIR)
    common.add_argument("--data-path", default=None,
                        help="Path to dataset file (required for sqa/drb).")
    common.add_argument("--subset", default="all",
                        choices=["all", "hard", "consensus"],
                        help="HealthBench subset.")
    common.add_argument("--grader-model", default="gpt-4.1-mini")

    # Claude Code arguments
    model_args = argparse.ArgumentParser(add_help=False)
    model_args.add_argument("--model", "-m", default="sonnet",
                            help="Claude model alias or full name (default: sonnet).")
    model_args.add_argument("--max-turns", type=int, default=15,
                            help="Max agentic turns per example.")
    model_args.add_argument("--max-budget-usd", type=float, default=None,
                            help="Max dollar spend per example.")
    model_args.add_argument(
        "--skill", "-s", default=None,
        choices=["deep-research", "literature-review", "fact-check", "research-coordinator"],
        help="Skill to use as system prompt (default: generic research prompt).",
    )

    # generate
    gen_parser = sub.add_parser("generate", parents=[common, model_args],
                                help="Generate responses only.")
    gen_parser.set_defaults(func=cmd_generate)

    # evaluate
    eval_parser = sub.add_parser("evaluate", parents=[common],
                                 help="Score an existing generation file.")
    eval_parser.add_argument("--generation-file", "-g", required=True,
                             help="Path to generation JSONL file.")
    eval_parser.set_defaults(func=cmd_evaluate)

    # run
    run_parser = sub.add_parser("run", parents=[common, model_args],
                                help="Generate + evaluate end-to-end.")
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
