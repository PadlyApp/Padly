"""
Debug CLI: print roommate behavioral fingerprints and pairwise similarity.

Usage (from backend/ with env configured for Supabase):
  PYTHONPATH=. python -m app.scripts.debug_roommate_similarity --user-a UUID --user-b UUID
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Roommate fingerprint / similarity debug")
    parser.add_argument("--user-a", required=True, help="users.id UUID")
    parser.add_argument("--user-b", required=True, help="users.id UUID")
    parser.add_argument("--days", type=int, default=180)
    args = parser.parse_args()

    if not os.environ.get("SUPABASE_URL") and not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print(
            "Warning: Supabase env not set; this script requires DB access.",
            file=sys.stderr,
        )

    from app.services.roommate_behavior_fingerprint import (
        build_roommate_behavior_fingerprint,
        fetch_personal_preferences_row,
        similarity_behavior,
    )

    fa = build_roommate_behavior_fingerprint(args.user_a, days=args.days)
    fb = build_roommate_behavior_fingerprint(args.user_b, days=args.days)
    pa = fetch_personal_preferences_row(args.user_a)
    pb = fetch_personal_preferences_row(args.user_b)

    sim = similarity_behavior(fa, fb, prefs_u=pa, prefs_v=pb)

    out = {
        "user_a": {"fingerprint": fa, "prefs_loaded": pa is not None},
        "user_b": {"fingerprint": fb, "prefs_loaded": pb is not None},
        "similarity": sim,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
