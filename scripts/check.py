"""Lightweight repository checks with no third-party dependencies."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EXPECTED_DOCS = {
    "00_Project_Map.md",
    "01_PRD.md",
    "02_System_Architecture.md",
    "03_Evaluation_Framework.md",
    "04_Dataset_Specification.md",
    "05_Spatial_Model_Specification.md",
    "06_Retrieval_Specification.md",
    "07_Technical_Decisions.md",
    "08_Repository_and_Data_Publication_Policy.md",
    "glossary.md",
    "open_questions.md",
}
REQUIRED_RULE_MARKERS = {
    "python3 -B scripts/check.py",
    "Never modify `main` directly.",
    "Documentation is the source of truth for implementation.",
    "Do not implement unconfirmed requirements.",
    "Do not use Computer Use unless it is genuinely necessary.",
    "PUBLIC_ALLOWED",
    "PRIVATE_ONLY",
    "REVIEW_REQUIRED",
    "Ground Truth is an evaluation authority",
    "Do not force push",
}


def check_markdown(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        errors.append(f"empty Markdown file: {path.relative_to(ROOT)}")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line != line.rstrip():
            errors.append(
                f"trailing whitespace: {path.relative_to(ROOT)}:{line_number}"
            )


def main() -> int:
    errors: list[str] = []

    if ROOT.name.casefold() != "amidst":
        errors.append(f"unexpected repository directory: {ROOT}")

    instructions = ROOT / "AGENTS.md"
    if not instructions.is_file():
        errors.append("missing AGENTS.md")
    else:
        check_markdown(instructions, errors)
        instruction_text = instructions.read_text(encoding="utf-8")
        for marker in sorted(REQUIRED_RULE_MARKERS):
            if marker not in instruction_text:
                errors.append(f"AGENTS.md is missing rule marker: {marker}")

    # The first bootstrap step intentionally runs before docs/ exists. Once any
    # documentation is added, require the complete planning-document set.
    if DOCS.exists():
        if not DOCS.is_dir():
            errors.append("docs exists but is not a directory")
        else:
            present = {path.name for path in DOCS.glob("*.md")}
            for missing in sorted(EXPECTED_DOCS - present):
                errors.append(f"missing documentation file: docs/{missing}")
            for path in sorted(DOCS.glob("*.md")):
                check_markdown(path, errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
