#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "qa_runs"

CASES = [
    {
        "title": "The Clockmaker's Reef",
        "synopsis": "A young diver discovers a broken machine city under the sea and must restart it before the tide erases its memory.",
        "pages": "6",
        "characters": "Mira,Otto,The Drowned Warden",
    },
    {
        "title": "Grandma's Tiny Dragon",
        "synopsis": "A shy child learns that the teacup dragon living in grandma's kitchen only grows when someone tells the truth.",
        "pages": "5",
        "characters": "June,Grandma,Ember",
    },
    {
        "title": "Receipt From Mars",
        "synopsis": "A cashier on a colony station discovers that a grocery receipt predicts accidents a few minutes before they happen.",
        "pages": "4",
        "characters": "Ilan,Rook,The Red Ledger",
    },
]

REAL_CASE = {
    "title": "Lantern Fish Promise",
    "synopsis": "A child follows a glowing fish through a dark reef and learns to bring light back home.",
    "pages": "3",
    "characters": "Lio,Nami,The Current",
}


def run(cmd: list[str]) -> str:
    completed = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def main() -> int:
    results = {"placeholder_cases": [], "real_case": None}
    OUT.mkdir(exist_ok=True)

    for case in CASES:
        out = run([
            "python3",
            "story_video_tool.py",
            "new",
            "--title",
            case["title"],
            "--synopsis",
            case["synopsis"],
            "--pages",
            case["pages"],
            "--characters",
            case["characters"],
            "--output-dir",
            str(OUT),
        ])
        summary = json.loads(out)
        run(["python3", "story_video_tool.py", "validate", summary["project_dir"]])
        results["placeholder_cases"].append(summary)

    real_out = run([
        "python3",
        "story_video_tool.py",
        "new",
        "--title",
        REAL_CASE["title"],
        "--synopsis",
        REAL_CASE["synopsis"],
        "--pages",
        REAL_CASE["pages"],
        "--characters",
        REAL_CASE["characters"],
        "--real-assets",
        "--output-dir",
        str(ROOT / "qa_runs_real"),
    ])
    real_summary = json.loads(real_out)
    run(["python3", "story_video_tool.py", "validate", real_summary["project_dir"]])
    run(["bash", real_summary["assemble_script"]])
    results["real_case"] = real_summary

    report_path = ROOT / "qa_report.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "report": str(report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
