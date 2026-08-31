from __future__ import annotations

import json
from urllib.parse import quote, unquote

from .checkpoints import Checkpoint

_FIELDS = ("T", "P", "S", "D", "F", "TP", "TF", "N")


def _q(value: str) -> str:
    return quote(value, safe="-_.~,/")


def encode_handoff(checkpoint: Checkpoint) -> str:
    decisions = json.dumps(checkpoint.decisions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    files = json.dumps(list(checkpoint.files_changed), separators=(",", ":"), ensure_ascii=False)
    values = (
        checkpoint.track, checkpoint.step, checkpoint.status, decisions, files,
        str(checkpoint.tests_passed), str(checkpoint.tests_failed), checkpoint.next_step or "",
    )
    return "H1;" + ";".join(f"{key}={_q(value)}" for key, value in zip(_FIELDS, values, strict=True))


def decode_handoff(text: str) -> Checkpoint:
    parts = text.split(";")
    if len(parts) != len(_FIELDS) + 1 or parts[0] != "H1":
        raise ValueError("invalid handoff envelope")
    values: dict[str, str] = {}
    for expected, part in zip(_FIELDS, parts[1:], strict=True):
        key, sep, value = part.partition("=")
        if not sep or key != expected or key in values:
            raise ValueError("invalid handoff field order or name")
        values[key] = unquote(value)
    try:
        decisions = json.loads(values["D"])
        files = json.loads(values["F"])
        if not isinstance(decisions, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in decisions.items()):
            raise ValueError("invalid decisions")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise ValueError("invalid files")
        passed = int(values["TP"]); failed = int(values["TF"])
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("invalid handoff payload") from exc
    return Checkpoint(
        track=values["T"], step=values["P"], status=values["S"], decisions=decisions,
        files_changed=tuple(files),
        tests_passed=passed, tests_failed=failed, next_step=values["N"] or None,
    )
