"""CLI entry point for the eval harness.

Usage:
    python -m evals.run run -b researchqa -n 5
    python -m evals.run run -b healthbench --subset hard -n 5 --skill research-coordinator
    python -m evals.run generate -b researchqa -n 10
    python -m evals.run evaluate -b researchqa -g evals/results/researchqa_gen.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from functools import partial
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def _get_benchmark(name: str, args: argparse.Namespace) -> Any:
    num = getattr(args, "num_examples", None)
    n_threads = getattr(args, "threads", 10)
    grader = getattr(args, "grader_model", "gpt-4.1-mini")
    output_dir = getattr(args, "output_dir", RESULTS_DIR)
    skill = getattr(args, "skill", None)  # None → benchmark default

    if name == "researchqa":
        from .benchmarks.researchqa import ResearchQAEval
        kw: dict[str, Any] = dict(
            data_path=getattr(args, "data_path", None),
            num_examples=num, n_threads=n_threads, grader_model=grader,
        )
        if skill is not None:
            kw["skill"] = skill
        return ResearchQAEval(**kw)

    if name == "healthbench":
        from .benchmarks.healthbench import HealthBenchEval
        kw = dict(
            subset=getattr(args, "subset", "all"),
            num_examples=num, n_threads=n_threads, grader_model=grader,
        )
        if skill is not None:
            kw["skill"] = skill
        return HealthBenchEval(**kw)

    if name == "sqa":
        from .benchmarks.sqa import SQAEval
        data_path = getattr(args, "data_path", None)
        kw: dict[str, Any] = dict(num_examples=num,
                   n_threads=n_threads, output_dir=output_dir)
        if data_path is not None:
            kw["data_path"] = data_path
        if skill is not None:
            kw["skill"] = skill
        return SQAEval(**kw)

    if name == "drb":
        from .benchmarks.drb import DRBEval
        data_path = getattr(args, "data_path", None)
        kw = dict(num_examples=num,
                   n_threads=n_threads, output_dir=output_dir)
        if data_path is not None:
            kw["data_path"] = data_path
        if skill is not None:
            kw["skill"] = skill
        return DRBEval(**kw)

    sys.exit(f"Error: unknown benchmark '{name}'")


def _make_run(args: argparse.Namespace):
    """Build a ``run_claude`` partial with CLI-level config baked in."""
    from .claude import run_claude
    return partial(
        run_claude,
        model=getattr(args, "model", "sonnet"),
        max_turns=getattr(args, "max_turns", 15),
        max_budget_usd=getattr(args, "max_budget_usd", None),
    )


def _print_results(benchmark_name: str, eval_result) -> None:
    print(f"\n{'='*60}")
    print(f"Benchmark: {benchmark_name}")
    if eval_result.score is not None:
        print(f"Score: {eval_result.score:.4f}")
    else:
        print("Score: N/A (external eval needed)")
    if eval_result.metrics:
        for k, v in sorted(eval_result.metrics.items()):
            if not k.endswith((":std", ":bootstrap_std")):
                print(f"  {k}: {v:.4f}")
    print(f"{'='*60}\n")


def cmd_generate(args: argparse.Namespace) -> None:
    benchmark = _get_benchmark(args.benchmark, args)
    run = _make_run(args)

    logger.info("Generating with %s on %s", args.model, args.benchmark)
    gen_data = benchmark.generate(run)

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"{args.benchmark}_gen.jsonl")
    with open(out_path, "w") as f:
        for row in gen_data:
            f.write(json.dumps(row, default=str) + "\n")
    logger.info("Saved %d generations to %s", len(gen_data), out_path)


def cmd_evaluate(args: argparse.Namespace) -> None:
    benchmark = _get_benchmark(args.benchmark, args)
    gen_path = args.generation_file
    if not os.path.exists(gen_path):
        sys.exit(f"Error: file not found: {gen_path}")

    with open(gen_path) as f:
        gen_data = [json.loads(line) for line in f if line.strip()]

    logger.info("Evaluating %d examples from %s", len(gen_data), gen_path)
    results = benchmark.evaluate(gen_data)

    from .common import aggregate_results
    eval_result = aggregate_results(results)
    _print_results(args.benchmark, eval_result)

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"{args.benchmark}_eval.json")
    with open(out_path, "w") as f:
        json.dump({"score": eval_result.score, "metrics": eval_result.metrics},
                  f, indent=2, default=str)
    logger.info("Saved eval results to %s", out_path)


def cmd_run(args: argparse.Namespace) -> None:
    benchmark = _get_benchmark(args.benchmark, args)
    run = _make_run(args)

    logger.info("Running %s end-to-end with %s", args.benchmark, args.model)
    gen_data, eval_result = benchmark(run)
    _print_results(args.benchmark, eval_result)

    os.makedirs(args.output_dir, exist_ok=True)

    # Save full generation data (includes trajectories).
    gen_path = os.path.join(args.output_dir, f"{args.benchmark}_gen.jsonl")
    with open(gen_path, "w") as f:
        for row in gen_data:
            f.write(json.dumps(row, default=str) + "\n")
    logger.info("Saved %d generations to %s", len(gen_data), gen_path)

    # Save eval scores.
    eval_path = os.path.join(args.output_dir, f"{args.benchmark}_eval.json")
    with open(eval_path, "w") as f:
        json.dump({"score": eval_result.score, "metrics": eval_result.metrics},
                  f, indent=2, default=str)
    logger.info("Saved eval results to %s", eval_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m evals.run",
        description="Eval harness for paper/paper-search CLI tools (uses Claude Code)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--benchmark", "-b", required=True,
                        choices=["researchqa", "healthbench", "sqa", "drb"])
    common.add_argument("--num-examples", "-n", type=int, default=None)
    common.add_argument("--threads", type=int, default=10)
    common.add_argument("--output-dir", default=RESULTS_DIR)
    common.add_argument("--data-path", default=None)
    common.add_argument("--subset", default="all", choices=["all", "hard", "consensus"])
    common.add_argument("--grader-model", default="gpt-4.1-mini")
    common.add_argument("--skill", "-s", default=None,
                        help="Skill slash command (default: benchmark-specific). "
                             "Use '' to disable.")

    model_args = argparse.ArgumentParser(add_help=False)
    model_args.add_argument("--model", "-m", default="sonnet")
    model_args.add_argument("--max-turns", type=int, default=15)
    model_args.add_argument("--max-budget-usd", type=float, default=None)

    p = sub.add_parser("generate", parents=[common, model_args])
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("evaluate", parents=[common])
    p.add_argument("--generation-file", "-g", required=True)
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("run", parents=[common, model_args])
    p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    # --skill '' means no skill
    if getattr(args, "skill", None) == "":
        args.skill = None
    args.func(args)


if __name__ == "__main__":
    main()
