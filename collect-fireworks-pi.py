#!/usr/bin/python3
"""Write a Fireworks usage record from Pi/omp sessions.

Omarchy's official fireworks collector only talks to the billing API.
Pi sessions that ran on provider \"fireworks\" never appear there, and
without an API key that collector writes an empty unavailable record.
This fills fireworks.json from local Pi/omp transcripts unless the
official record already has account-scoped billing numbers.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

AGENT_ID = "fireworks"
AGENT_NAME = "Fireworks"


def expand_path(value: str) -> Path:
  return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def usage_path() -> Path:
  root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
  folder = root / "omarchy" / "agents" / "usage"
  folder.mkdir(parents=True, exist_ok=True)
  return folder / "fireworks.json"


def date_string(value: dt.date) -> str:
  return value.strftime("%Y-%m-%d")


def local_date_string() -> str:
  return date_string(dt.datetime.now().date())


def recent_date_strings() -> list[str]:
  today = dt.datetime.now().date()
  return [date_string(today - dt.timedelta(days=offset)) for offset in range(6, -1, -1)]


def local_date_from_timestamp(value: Any) -> str:
  if value is None:
    return local_date_string()
  if isinstance(value, (int, float)):
    try:
      seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
      return date_string(dt.datetime.fromtimestamp(seconds).date())
    except Exception:
      return local_date_string()
  raw = str(value).strip()
  if not raw:
    return local_date_string()
  try:
    parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
      parsed = parsed.astimezone()
    return date_string(parsed.date())
  except Exception:
    return local_date_string()


def number(value: Any) -> int:
  try:
    n = float(value or 0)
    return round(n) if n == n else 0
  except Exception:
    return 0


def empty_bucket() -> dict[str, int]:
  return {
    "inputTokens": 0,
    "outputTokens": 0,
    "cacheReadInputTokens": 0,
    "cacheCreationInputTokens": 0,
  }


def model_name(raw: Any) -> str:
  name = str(raw or "fireworks").rstrip("/").split("/")[-1]
  return name or "fireworks"


def record_tokens(record: dict[str, Any]) -> int:
  usage = record.get("modelUsage") or {}
  total = 0
  for bucket in usage.values():
    if isinstance(bucket, dict):
      total += (
        number(bucket.get("inputTokens"))
        + number(bucket.get("outputTokens"))
        + number(bucket.get("cacheReadInputTokens"))
        + number(bucket.get("cacheCreationInputTokens"))
      )
  week = 0
  for day in record.get("recentDays") or []:
    if isinstance(day, dict):
      week += number(day.get("messageCount"))
  return max(total, week, number(record.get("todayTotalTokens")))


def official_billing_record(path: Path) -> dict[str, Any] | None:
  try:
    parsed = json.loads(path.read_text(encoding="utf-8"))
  except Exception:
    return None
  if not isinstance(parsed, dict):
    return None
  if parsed.get("source") == "pi":
    return None
  if str(parsed.get("scope") or "") != "account":
    return None
  if parsed.get("ready") is True and record_tokens(parsed) > 0:
    return parsed
  return None


def scan_pi() -> dict[str, Any] | None:
  roots = [
    Path.home() / ".pi" / "agent" / "sessions",
    Path.home() / ".omp" / "agent" / "sessions",
  ]
  today = local_date_string()
  recent_dates = recent_date_strings()
  recent = {day: {"date": day, "messageCount": 0} for day in recent_dates}
  sessions: set[str] = set()
  active_days: set[str] = set()
  today_sessions: set[str] = set()
  today_tokens: dict[str, int] = {}
  usage_by_model: dict[str, dict[str, int]] = {}
  seen: set[str] = set()
  prompts = 0
  today_prompt_count = 0
  today_token_total = 0

  for root in roots:
    files = root.rglob("*.jsonl") if root.is_dir() else []
    for path in files:
      try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
          for line_number, line in enumerate(handle, 1):
            if '"fireworks"' not in line or '"usage"' not in line:
              continue
            try:
              entry = json.loads(line)
              message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
              if entry.get("type") != "message" or message.get("role") != "assistant":
                continue
              if str(message.get("provider") or "") != "fireworks":
                continue
              unique_key = f"{path}:{entry.get('id') or line_number}"
              if unique_key in seen:
                continue
              seen.add(unique_key)
              usage = message.get("usage") or {}
              input_tokens = number(usage.get("input") or usage.get("inputTokens"))
              output_tokens = number(usage.get("output") or usage.get("outputTokens"))
              cache_read = number(usage.get("cacheRead") or usage.get("cache_read_input_tokens"))
              cache_write = number(usage.get("cacheWrite") or usage.get("cache_creation_input_tokens"))
              total = input_tokens + output_tokens + cache_read + cache_write
              if total <= 0:
                total = number(usage.get("totalTokens"))
                input_tokens = total
              if total <= 0:
                continue
              model = model_name(message.get("model") or message.get("modelId"))
              day = local_date_from_timestamp(entry.get("timestamp") or message.get("timestamp"))
            except Exception:
              continue

            session_key = str(path)
            sessions.add(session_key)
            active_days.add(day)
            prompts += 1
            bucket = usage_by_model.setdefault(model, empty_bucket())
            bucket["inputTokens"] += input_tokens
            bucket["outputTokens"] += output_tokens
            bucket["cacheReadInputTokens"] += cache_read
            bucket["cacheCreationInputTokens"] += cache_write
            if day in recent:
              recent[day]["messageCount"] += total
            if day == today:
              today_prompt_count += 1
              today_sessions.add(session_key)
              today_token_total += total
              today_tokens[model] = today_tokens.get(model, 0) + total
      except OSError:
        continue

  if prompts <= 0:
    return None
  return {
    "todayPrompts": today_prompt_count,
    "todaySessions": len(today_sessions),
    "todayTotalTokens": today_token_total,
    "todayTokensByModel": today_tokens,
    "recentDays": [recent[day] for day in recent_dates],
    "modelUsage": usage_by_model,
    "totalPrompts": prompts,
    "totalSessions": len(sessions),
    "activeDays": len(active_days),
    "activeDates": sorted(active_days),
  }


def write_json(path: Path, payload: dict[str, Any]) -> None:
  handle_fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
  tmp = Path(tmp_name)
  try:
    with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
      handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    tmp.chmod(0o644)
    tmp.replace(path)
  except BaseException:
    tmp.unlink(missing_ok=True)
    raise


def main() -> int:
  path = usage_path()
  if official_billing_record(path) is not None:
    return 0
  stats = scan_pi()
  if stats is None:
    return 0
  record = {
    "schemaVersion": 1,
    "id": AGENT_ID,
    "name": AGENT_NAME,
    "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    "ready": True,
    "hasLocalStats": True,
    "hasPromptStats": True,
    "scope": "device",
    "source": "pi",
    "tierLabel": "Pi",
    "usageStatusText": "",
    "authHelpText": "",
    "limits": [],
  }
  record.update(stats)
  write_json(path, record)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
