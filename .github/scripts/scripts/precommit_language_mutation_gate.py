"""Run mutmut against repository Python source files.

The mutmut native config accepts directories or explicit paths, but a broad
directory path also copies ignored runtime trees into the mutant workspace.
This wrapper keeps the hook generic by discovering Python files from Git and
passing the current source set to mutmut programmatically.
"""

from __future__ import annotations

import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
from functools import wraps
from pathlib import Path
from typing import Any

import mutmut.configuration as mutmut_configuration
from mutmut.configuration import Config
from mutmut.mutation.data import SourceFileMutationData

EXCLUDED_DIRS = {
    ".agents",
    ".codex",
    ".github",
    ".gsd",
    ".skills",
    ".skillss",
    ".venv",
    "mutants",
    "skills",
    "tests",
}

ALSO_COPY = [
    Path("tests"),
    Path("test"),
    Path("pyproject.toml"),
    Path("README.md"),
    Path("src"),
]


def _git_python_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _fallback_python_files(root: Path) -> list[Path]:
    return [path.relative_to(root) for path in root.rglob("*.py") if path.is_file()]


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts[:-1])


def discover_python_sources(root: Path) -> list[Path]:
    try:
        candidates = _git_python_files(root)
    except (FileNotFoundError, subprocess.CalledProcessError):
        candidates = _fallback_python_files(root)

    sources = [path for path in candidates if not _is_excluded(path)]
    return sorted(set(sources), key=lambda path: path.as_posix())


def configure_mutmut(source_paths: list[Path]) -> None:
    mutmut_configuration._config = Config(
        also_copy=ALSO_COPY,
        only_mutate=["*.py"],
        do_not_mutate=[
            "tests/*",
            "./tests/*",
            ".github/*",
            "./.github/*",
            ".agents/*",
            "./.agents/*",
            ".codex/*",
            "./.codex/*",
            ".gsd/*",
            "./.gsd/*",
            ".skillss/*",
            "./.skillss/*",
            ".skills/*",
            "./.skills/*",
            ".venv/*",
            "./.venv/*",
            "skills/*",
            "./skills/*",
            "mutants/*",
            "./mutants/*",
        ],
        do_not_mutate_patterns=[],
        max_stack_depth=-1,
        debug=True,
        mutate_only_covered_lines=True,
        source_paths=source_paths,
        pytest_add_cli_args=["-x", "-q", "--tb=no"],
        pytest_add_cli_args_test_selection=["tests"],
        timeout_multiplier=2.0,
        timeout_constant=1.0,
        type_check_command=[],
        use_setproctitle=platform.system() != "Darwin",
    )


def print_results() -> None:
    from mutmut.__main__ import status_by_exit_code, walk_mutatable_files

    for path in walk_mutatable_files():
        mutation_data = SourceFileMutationData(path=path)
        mutation_data.load()
        for mutant_name, exit_code in mutation_data.exit_code_by_key.items():
            status = status_by_exit_code[exit_code]
            if status == "killed":
                continue
            print(f"    {mutant_name}: {status}")


def warm_imports() -> None:
    """Hook for project-specific import warmups.

    Keep this empty unless a future runtime dependency needs eager import setup
    inside mutmut's worker process.
    """


def normalize_src_module_name(name: str) -> str:
    """Map this repo's top-level src package to mutmut's src-layout module names."""
    if name.startswith("src."):
        return name[4:]
    if name == "src":
        return ""
    return name


def patch_mutmut_src_package_trampoline() -> None:  # noqa: C901
    """Let mutmut handle this repository's `src.*` imports.

    Mutmut derives mutant keys from files under `src/` as `core.foo`, while this
    project imports those modules as `src.core.foo`. Without normalization,
    mutmut either rejects the trampoline hit or never activates matching mutants.
    """
    import mutmut.mutation.trampoline as trampoline_module
    from mutmut.__main__ import (
        MutmutProgrammaticFailException,
        mangled_name_from_mutant_name,
        record_trampoline_hit,
    )

    def record_normalized_trampoline_hit(name: str) -> None:
        record_trampoline_hit(normalize_src_module_name(name))

    def wrap_in_trampoline(mutants_dict: dict[str, Any], is_classmethod: bool = False) -> Any:  # noqa: C901
        def mutmut_mutated(decorated_func: Any) -> Any:  # noqa: C901
            def trampoline(*args: Any, **kwargs: Any) -> Any:
                orig_func = mutants_dict["_mutmut_orig"]
                call_args = list(args)

                if is_classmethod:
                    call_args = list(args[1:])
                    orig_func = getattr(args[0], orig_func.__name__)

                mutant_under_test = os.environ.get("MUTANT_UNDER_TEST", "")

                if mutant_under_test == "fail":
                    raise MutmutProgrammaticFailException(
                        "Verifying setup. At least one test should fail if mutations cause errors."
                    )

                if mutant_under_test == "stats":
                    record_normalized_trampoline_hit(
                        f"{orig_func.__module__}.{mangled_name_from_mutant_name(orig_func.__name__)}"
                    )
                    return orig_func(*call_args, **kwargs)

                module, _, mutant_name = mutant_under_test.rpartition(".")
                if module != normalize_src_module_name(decorated_func.__module__):
                    return orig_func(*call_args, **kwargs)

                mutated_func = mutants_dict.get(mutant_name)
                if mutated_func is None:
                    return orig_func(*call_args, **kwargs)

                if is_classmethod:
                    mutated_func = getattr(args[0], mutated_func.__name__)
                return mutated_func(*call_args, **kwargs)

            if inspect.isgeneratorfunction(decorated_func):

                @wraps(decorated_func)
                def _trampoline_wrapper(*args: Any, **kwargs: Any) -> Any:
                    yield from trampoline(*args, **kwargs)

            elif inspect.iscoroutinefunction(decorated_func):

                @wraps(decorated_func)
                async def _trampoline_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return await trampoline(*args, **kwargs)

            elif inspect.isasyncgenfunction(decorated_func):

                @wraps(decorated_func)
                async def _trampoline_wrapper(*args: Any, **kwargs: Any) -> Any:
                    async for result in trampoline(*args, **kwargs):
                        yield result

            else:

                @wraps(decorated_func)
                def _trampoline_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return trampoline(*args, **kwargs)

            return _trampoline_wrapper

        return mutmut_mutated

    trampoline_module.record_trampoline_hit = record_normalized_trampoline_hit
    trampoline_module.wrap_in_trampoline = wrap_in_trampoline


def prepare_cached_coverage(root: Path) -> bool:
    """Copy the prior slow-lane coverage database when the matrix artifact has it."""
    coverage_source = root / "build/slow-lane/.coverage"
    coverage_target = root / ".coverage"
    if not coverage_source.exists():
        print("Cached coverage file not found; mutmut will collect coverage in this job.")
        return False
    if coverage_source.stat().st_size == 0:
        print("Cached coverage file is empty; mutmut will collect coverage in this job.")
        return False

    shutil.copy2(coverage_source, coverage_target)
    return True


def _coverage_line_candidates(root: Path, filename: Path) -> tuple[str, ...]:
    """Return coverage.py keys used by local and CI coverage databases."""
    return (
        filename.as_posix(),
        str(filename),
        str((root / filename).resolve()),
        str((root / "mutants" / filename).resolve()),
    )


def _lookup_coverage_lines(coverage_data: Any, root: Path, filename: Path) -> set[int]:
    """Find covered lines for a source file across relative and absolute coverage keys."""
    for candidate in _coverage_line_candidates(root, filename):
        lines = coverage_data.lines(candidate)
        if lines:
            return set(lines)

    suffix = filename.as_posix()
    for measured_file in coverage_data.measured_files():
        if measured_file.endswith(suffix):
            lines = coverage_data.lines(measured_file)
            if lines:
                return set(lines)

    return set()


def patch_mutmut_coverage(coverage_file: Path) -> None:
    """Make mutmut reuse our existing .coverage and handle relative_files=true."""
    import mutmut.__main__
    import mutmut.code_coverage

    original_gather_coverage = mutmut.code_coverage.gather_coverage
    root = Path.cwd()

    def patched_gather_coverage(runner: Any, source_files: list[Path]) -> dict[str, set[int]]:
        import coverage

        cov = coverage.Coverage(data_file=str(coverage_file))
        cov.load()
        coverage_data = cov.get_data()

        covered_lines: dict[str, set[int]] = {}
        mutants_path = Path("mutants")
        for filename in source_files:
            abs_filename = str((mutants_path / filename).absolute())
            covered_lines[abs_filename] = _lookup_coverage_lines(coverage_data, root, filename)

        if not any(covered_lines.values()):
            print("Cached coverage had no lines for selected files; falling back to mutmut coverage collection.")
            return original_gather_coverage(runner, source_files)

        return covered_lines

    mutmut.code_coverage.gather_coverage = patched_gather_coverage
    mutmut.__main__.gather_coverage = patched_gather_coverage


def clean_corrupt_mutmut_metadata(root: Path) -> list[Path]:
    """Remove ignored mutmut metadata files that cannot be decoded as JSON."""
    mutants_dir = root / "mutants"
    if not mutants_dir.exists():
        return []

    removed: list[Path] = []
    for metadata_path in mutants_dir.rglob("*.meta"):
        try:
            with metadata_path.open() as metadata_file:
                json.load(metadata_file)
        except (OSError, json.JSONDecodeError):
            metadata_path.unlink(missing_ok=True)
            removed.append(metadata_path)
    return removed


def reset_mutmut_workspace(root: Path) -> None:
    """Drop mutmut's ignored generated workspace so hooks use current source."""
    shutil.rmtree(root / "mutants", ignore_errors=True)


def _mutmut_status() -> int:
    from mutmut.__main__ import _run

    try:
        _run((), None)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def run_mutmut_once(root: Path) -> int:
    try:
        return _mutmut_status()
    except json.JSONDecodeError:
        removed = clean_corrupt_mutmut_metadata(root)
        if not removed:
            raise
        print(f"Removed {len(removed)} corrupt mutmut metadata files; retrying language mutation.")
        return _mutmut_status()


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    argv = argv if argv is not None else sys.argv[1:]
    root = Path.cwd()

    chunk_index = 0
    total_chunks = 1

    filtered_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--chunk" and i + 1 < len(argv):
            chunk_index = int(argv[i + 1])
            i += 2
        elif argv[i] == "--total-chunks" and i + 1 < len(argv):
            total_chunks = int(argv[i + 1])
            i += 2
        else:
            filtered_argv.append(argv[i])
            i += 1
    argv = filtered_argv

    if argv == ["--check-config"]:
        source_paths = discover_python_sources(root)
        print(f"language mutation source files: {len(source_paths)}")
        print(f"excluded directories: {', '.join(sorted(EXCLUDED_DIRS))}")
        return 0

    if argv:
        candidates = [Path(p) for p in argv]
        source_paths = [path for path in candidates if not _is_excluded(path)]
        source_paths = sorted(set(source_paths), key=lambda path: path.as_posix())
    else:
        source_paths = discover_python_sources(root)

    if total_chunks > 1:
        source_paths = [p for i, p in enumerate(source_paths) if i % total_chunks == chunk_index]

    configure_mutmut(source_paths)

    if not source_paths:
        print("No production Python source files found; skipping language mutation gate.")
        return 0

    if not (root / "tests").is_dir():
        print("No tests directory found; skipping language mutation gate until tests exist.")
        return 0

    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONPATH"] = ""

    coverage_target = root / ".coverage"
    copied_coverage = prepare_cached_coverage(root)

    warm_imports()
    patch_mutmut_src_package_trampoline()
    if copied_coverage:
        patch_mutmut_coverage(coverage_target)
    reset_mutmut_workspace(root)

    status = 0
    try:
        status = run_mutmut_once(root)
    finally:
        if copied_coverage:
            coverage_target.unlink(missing_ok=True)

    print_results()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
