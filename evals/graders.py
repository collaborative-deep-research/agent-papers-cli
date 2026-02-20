"""LLM-based grading: coverage scoring (ResearchQA) and rubric scoring (HealthBench).

Uses OpenAI client by default (gpt-4.1-mini) but the model is configurable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _call_llm(prompt: str, model: str = "gpt-4.1-mini") -> str:
    """Single-turn LLM call via OpenAI client."""
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Coverage grading (ResearchQA)
# ---------------------------------------------------------------------------

COVERAGE_PROMPT_TEMPLATE = """\
Please judge the following questions based on the response below.
For each question, select one of the following ratings to indicate the extent \
to which the response addresses the question:
Not at all, Barely, Moderately, Mostly, Completely

Definitions:
- Not at all: *totally uninferable*
- Barely: *unmentioned but inferrable*
- Moderately: *mentioned but misses important details*
- Mostly: *mentioned but misses some details*
- Completely: *mentioned with sufficient details*

Only output one of the five phrases for each question, separated by newlines, \
and nothing else.

Response: {response}
Questions:
{questions}

Output:"""

_TEXT_TO_SCORE = {
    "Not at all": 1,
    "Barely": 2,
    "Moderately": 3,
    "Mostly": 4,
    "Completely": 5,
}


def _normalize_5scale(x: int) -> float:
    return (x - 1) / 4


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8))
def _process_coverage_batch(
    response_text: str,
    questions: list[str],
    model: str,
) -> list[str]:
    """Send a batch of rubric items and return per-item scores with retry."""
    prompt = COVERAGE_PROMPT_TEMPLATE.format(
        response=response_text,
        questions="\n".join(questions),
    )
    raw = _call_llm(prompt, model=model)
    scores = [s.strip() for s in raw.split("\n") if s.strip()]
    if len(scores) != len(questions):
        raise ValueError(
            f"Expected {len(questions)} scores, got {len(scores)}"
        )
    return scores


def grade_coverage(
    response_text: str,
    rubric_items: list[str],
    model: str = "gpt-4.1-mini",
    batch_size: int = 8,
) -> tuple[float, list[dict[str, Any]]]:
    """Grade how well *response_text* covers each rubric item.

    Returns ``(coverage_score, rubric_judges)`` where coverage_score is in
    [0, 1] and rubric_judges is a list of ``{rubric, score}`` dicts.
    """
    rubric_judges: list[dict[str, Any]] = []

    for i in range(0, len(rubric_items), batch_size):
        batch = rubric_items[i : i + batch_size]
        try:
            scores = _process_coverage_batch(response_text, batch, model)
            for rubric, score_text in zip(batch, scores):
                rubric_judges.append({"rubric": rubric, "score": score_text})
        except Exception:
            logger.error("Coverage batch failed after retries, skipping batch %d", i)
            for rubric in batch:
                rubric_judges.append({"rubric": rubric, "score": "Not at all"})

    # Compute average normalised score
    numeric = [_TEXT_TO_SCORE.get(j["score"], 1) for j in rubric_judges]
    normalised = [_normalize_5scale(x) for x in numeric]
    coverage_score = sum(normalised) / len(normalised) if normalised else 0.0

    return coverage_score, rubric_judges


# ---------------------------------------------------------------------------
# Rubric grading (HealthBench)
# ---------------------------------------------------------------------------

RUBRIC_GRADER_TEMPLATE = """\
Your job is to look at a conversation and a rubric item, and score the last \
turn (i.e., the last assistant response, or the completion) in the \
conversation on how well it follows the rubric item.

# Conversation
{conversation}

# Rubric item
{rubric_item}

# Instructions
Return a json object with the following fields: "explanation" and "criteria_met".
- The "explanation" field should be a string explaining why the response does \
or does not meet the criteria of the rubric item.
- The "criteria_met" field should be a boolean indicating whether the response \
meets the criteria of the rubric item. If a rubric item has multiple sentences \
or criteria, you should consider all of them. If any of the criteria is not \
met, the answer should be false. Only return true if all of the criteria are met.
- One important exception: if a criteria says "such as", "for example", or \
"including", the response does not have to include all examples listed.

Return just the json object in markdown format. Do not include any other text.
"""


def _parse_grader_json(text: str) -> dict[str, Any]:
    """Parse JSON from LLM grader output, stripping markdown fences."""
    cleaned = re.sub(r"^```json\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8))
def _grade_single_rubric(
    conversation_str: str,
    rubric_text: str,
    model: str,
) -> dict[str, Any]:
    """Grade a single rubric item with retry."""
    prompt = RUBRIC_GRADER_TEMPLATE.format(
        conversation=conversation_str,
        rubric_item=rubric_text,
    )
    raw = _call_llm(prompt, model=model)
    result = _parse_grader_json(raw)
    if "criteria_met" not in result:
        raise ValueError("Grader output missing 'criteria_met'")
    if result["criteria_met"] not in (True, False):
        raise ValueError(f"Invalid criteria_met value: {result['criteria_met']}")
    return result


def grade_rubric(
    prompt_messages: list[dict[str, str]],
    response_text: str,
    rubric_items: list[dict[str, Any]],
    model: str = "gpt-4.1-mini",
) -> tuple[float, list[dict[str, Any]]]:
    """Grade *response_text* against HealthBench-style rubric items.

    Each item in *rubric_items* should have ``criterion``, ``points``, and
    ``tags`` keys.

    Returns ``(score, grading_results)`` where score = achieved / total
    possible points and grading_results is the list of grader outputs.
    """
    convo_messages = prompt_messages + [{"role": "assistant", "content": response_text}]
    convo_str = "\n\n".join(f"{m['role']}: {m['content']}" for m in convo_messages)

    grading_results: list[dict[str, Any]] = []
    for item in rubric_items:
        rubric_text = f"[{item['points']}] {item['criterion']}"
        try:
            result = _grade_single_rubric(convo_str, rubric_text, model)
        except Exception:
            logger.error("Rubric grading failed for: %s", item["criterion"][:60])
            result = {
                "criteria_met": False,
                "explanation": "Grading failed after retries.",
            }
        grading_results.append({**item, **result})

    # Score = achieved_points / total_possible_points
    total_possible = sum(item["points"] for item in rubric_items if item["points"] > 0)
    if total_possible == 0:
        return 0.0, grading_results

    achieved = sum(
        item["points"]
        for item, grade in zip(rubric_items, grading_results)
        if grade["criteria_met"]
    )
    score = achieved / total_possible
    return score, grading_results
