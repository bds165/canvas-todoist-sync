"""Entry point: python -m canvas_todoist [--dry-run]."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from canvas_todoist.calendar_feed import CalendarFeedSource
from canvas_todoist.config import load_config, load_secrets
from canvas_todoist.engine import SyncAborted, run_sync
from canvas_todoist.state import load_state, save_state
from canvas_todoist.todoist_http import TodoistHttpGateway

log = logging.getLogger("canvas_todoist")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Canvas Assignments into Todoist.")
    parser.add_argument("--dry-run", action="store_true", help="log what would change; write nothing")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # urllib3 logs request lines at DEBUG only, but pin it so the feed address can't leak.
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    try:
        config = load_config(args.config)
        if args.dry_run:
            config = dataclasses.replace(config, dry_run=True)
        secrets = load_secrets()
        session = requests.Session()
        result = run_sync(
            CalendarFeedSource(secrets.calendar_feed_url, session),
            TodoistHttpGateway(secrets.todoist_token, session),
            load_state(args.state),
            config,
            datetime.now(timezone.utc),
        )
    except SyncAborted as aborted:
        # Keep the record of Synced Tasks already created, so the next run doesn't duplicate them.
        if not config.dry_run:
            save_state(args.state, aborted.result.state)
        log.error("Sync failed partway (%s): %s", aborted.result.summary, aborted.__cause__)
        return 1
    except Exception as exc:
        # Adapters keep secrets out of their messages; no traceback, so no locals either.
        log.error("Sync failed: %s", exc)
        return 1

    if result.retired:
        print("Sync retired")
        _set_workflow_output("retired", "true")
        return 0
    if not config.dry_run:
        save_state(args.state, result.state)
    print(f"{'Dry run: ' if config.dry_run else ''}{result.summary}")
    return 0


def _set_workflow_output(name: str, value: str) -> None:
    """Pass a value to later GitHub Actions steps; does nothing outside Actions."""
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as file:
            file.write(f"{name}={value}\n")


if __name__ == "__main__":
    sys.exit(main())
