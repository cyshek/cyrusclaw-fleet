"""Shared model-invocation config for the job-search pipeline.

Single source of truth for which LLM the pipeline calls (resume tailoring,
essay/cover answers, why-company fallback).

Default behavior: DO NOT pass --model, so `openclaw capability model run`
inherits the agent's CURRENT default model — i.e. the same model powering the
job-search agent itself. This means when Cyrus upgrades the agent's model,
the pipeline follows automatically with no code edits.

Override: set env JOBSEARCH_MODEL=provider/model to pin a specific model
(e.g. for cost control). Empty/unset = inherit.

Usage:
    from model_config import model_run_cmd
    cmd = model_run_cmd(prompt)            # inherits agent model
    cmd = model_run_cmd(prompt, json=True)
"""
from __future__ import annotations

import os

# Optional hard pin. Leave unset/empty to inherit the agent's current model.
PINNED_MODEL = os.environ.get("JOBSEARCH_MODEL", "").strip()


def model_run_cmd(prompt: str | None = None, *, json: bool = True,
                  thinking: str | None = None) -> list[str]:
    """Build the `openclaw capability model run` argv.

    When no model is pinned via JOBSEARCH_MODEL, --model is omitted entirely so
    the call inherits the agent's configured default model (the model powering
    this agent). Pass prompt=None to get the base command and append --prompt
    yourself.
    """
    cmd = ["openclaw", "infer", "model", "run"]
    if PINNED_MODEL:
        cmd += ["--model", PINNED_MODEL]
    if json:
        cmd += ["--json"]
    if thinking:
        cmd += ["--thinking", thinking]
    if prompt is not None:
        cmd += ["--prompt", prompt]
    else:
        cmd += ["--prompt"]
    return cmd
