"""Lightweight repository checks with no third-party dependencies."""

from __future__ import annotations

from pathlib import Path
import re
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
    "09_Data_Types_and_Exchange_Formats.md",
    "10_Cross_Platform_Setup_and_Testing.md",
    "glossary.md",
    "internal_guide.md",
    "open_questions.md",
}
REQUIRED_INTERNAL_GUIDE_MARKERS = {
    "## Cross-Platform Continuation",
    "## Decision Status",
    "## Information Review Mechanisms",
    "## Publication Workflow",
    "## 繁體中文",
    "python3 -B scripts/check.py",
}
REQUIRED_DATA_TYPE_GUIDE_MARKERS = {
    "Document status: `PROPOSED`",
    "## Blender and Spatial Data",
    "## Portable Path Contract",
    "## Video Asset and Stream Metadata",
    "## Video Event Record",
    "## ASAM OpenLABEL Compatibility Candidate",
}
REQUIRED_BILINGUAL_DOC_MARKERS = {
    "[English](#english)",
    "[繁體中文](#繁體中文)",
    "## English",
    "## 繁體中文",
}
REQUIRED_README_MARKERS = {
    "planning and specification",
    "繁體中文",
    "docs/00_Project_Map.md",
    "docs/08_Repository_and_Data_Publication_Policy.md",
    "python3 -B scripts/check.py",
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
PORTABILITY_SCAN_ROOTS = (
    ROOT / "docs",
    ROOT / "scripts",
    ROOT / "blender/scripts",
    ROOT / "data/metadata",
)
REQUIRED_PROJECT_FILES = (
    ROOT / "requirements-dev.lock.txt",
    ROOT / "scripts/test.py",
    ROOT / "tests/test_migration_manifest.py",
    ROOT / "tests/test_repository_contracts.py",
    ROOT / "blender/runtime_dependencies.lock.json",
    ROOT / "blender/scripts/check_runtime_dependencies.py",
)
REQUIRED_SETUP_GUIDE_MARKERS = {
    "### macOS",
    "### Windows (PowerShell)",
    "### macOS 使用方式",
    "### Windows 使用方式（PowerShell）",
    "python3 -B scripts/test.py",
    "py -3 -B scripts/test.py",
}
PORTABILITY_SUFFIXES = {".json", ".md", ".py", ".ps1", ".sh", ".toml", ".yaml", ".yml"}
MACHINE_PATH_PATTERNS = (
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/Volumes/[^/\s]+/"),
    re.compile(r"\b[A-Za-z]:[\\/]Users[\\/][^\\/\s]+[\\/]"),
)


def check_markdown(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        errors.append(f"empty Markdown file: {path.relative_to(ROOT)}")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line != line.rstrip():
            errors.append(
                f"trailing whitespace: {path.relative_to(ROOT)}:{line_number}"
            )


def check_portable_active_files(errors: list[str]) -> None:
    for scan_root in PORTABILITY_SCAN_ROOTS:
        if not scan_root.is_dir():
            continue
        for path in sorted(candidate for candidate in scan_root.rglob("*") if candidate.is_file()):
            if path == Path(__file__).resolve():
                continue
            if path.suffix.casefold() not in PORTABILITY_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in MACHINE_PATH_PATTERNS):
                    errors.append(
                        "machine-specific absolute path in active file: "
                        f"{path.relative_to(ROOT)}:{line_number}"
                    )


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_PROJECT_FILES:
        if not path.is_file():
            errors.append(f"missing project file: {path.relative_to(ROOT)}")

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

    readme = ROOT / "README.md"
    if not readme.is_file():
        errors.append("missing README.md")
    else:
        check_markdown(readme, errors)
        readme_text = readme.read_text(encoding="utf-8")
        for marker in sorted(REQUIRED_README_MARKERS):
            if marker not in readme_text:
                errors.append(f"README.md is missing marker: {marker}")

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
                document_text = path.read_text(encoding="utf-8")
                for marker in sorted(REQUIRED_BILINGUAL_DOC_MARKERS):
                    if marker not in document_text:
                        errors.append(
                            f"{path.relative_to(ROOT)} is missing bilingual marker: "
                            f"{marker}"
                        )

            internal_guide = DOCS / "internal_guide.md"
            if internal_guide.is_file():
                guide_text = internal_guide.read_text(encoding="utf-8")
                for marker in sorted(REQUIRED_INTERNAL_GUIDE_MARKERS):
                    if marker not in guide_text:
                        errors.append(
                            f"docs/internal_guide.md is missing marker: {marker}"
                        )

            data_type_guide = DOCS / "09_Data_Types_and_Exchange_Formats.md"
            if data_type_guide.is_file():
                guide_text = data_type_guide.read_text(encoding="utf-8")
                for marker in sorted(REQUIRED_DATA_TYPE_GUIDE_MARKERS):
                    if marker not in guide_text:
                        errors.append(
                            "docs/09_Data_Types_and_Exchange_Formats.md "
                            f"is missing marker: {marker}"
                        )

            setup_guide = DOCS / "10_Cross_Platform_Setup_and_Testing.md"
            if setup_guide.is_file():
                guide_text = setup_guide.read_text(encoding="utf-8")
                for marker in sorted(REQUIRED_SETUP_GUIDE_MARKERS):
                    if marker not in guide_text:
                        errors.append(
                            "docs/10_Cross_Platform_Setup_and_Testing.md "
                            f"is missing marker: {marker}"
                        )

    check_portable_active_files(errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
