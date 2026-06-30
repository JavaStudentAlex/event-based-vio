"""Minimal APS mutation worker for the repository quality gate.

The APS mutator requires an executable persistent worker even when current
features have no example rows to mutate. This worker keeps that protocol in
place and fails explicitly if a real mutation job is sent before the project has
generated acceptance tests wired to mutated feature IR.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "id": "",
                "outcome": "infrastructure_error",
                "output": "",
                "error": f"invalid mutation request JSON: {exc}",
                "duration": 0,
            }
        else:
            response = {
                "id": request.get("id", ""),
                "outcome": "infrastructure_error",
                "output": "",
                "error": (
                    "APS acceptance mutation runner is installed, but project-specific "
                    "generated acceptance tests are not wired for mutated feature IR yet."
                ),
                "duration": 0,
            }

        print(json.dumps(response, separators=(",", ":")), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
