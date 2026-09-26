"""合成コードと明示した比較コーパスの長いtoken一致を検査する。"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import token
import tokenize
import zipfile
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE = PROJECT_ROOT / "data/archives/final_train_dataset_records_2026-09-25.zip"
DEFAULT_MEMBER = "final_dataset_records.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/provenance/long_code_match_report.json"
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "data",
    "third_party",
    "web",
}
IGNORED_TOKEN_TYPES = {
    token.ENDMARKER,
    token.ENCODING,
    token.INDENT,
    token.DEDENT,
    token.NEWLINE,
    tokenize.NL,
    token.COMMENT,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="最終訓練コードと比較コーパスの長い字句列一致を検査します。"
    )
    parser.add_argument("--dataset-archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--dataset-member", default=DEFAULT_MEMBER)
    parser.add_argument(
        "--corpus",
        action="append",
        type=Path,
        default=None,
        help="比較対象の.pyまたはディレクトリ。複数指定可。省略時はリポジトリ直下。",
    )
    parser.add_argument("--minimum-tokens", type=int, default=24)
    parser.add_argument("--max-reported-matches", type=int, default=100)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-match", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_tokens(source: str) -> tuple[str, ...]:
    """空白とコメントを除いたPython字句列を返す。"""

    values: list[str] = []
    try:
        stream = tokenize.generate_tokens(io.StringIO(source).readline)
        for item in stream:
            if item.type not in IGNORED_TOKEN_TYPES:
                values.append(item.string)
    except (IndentationError, tokenize.TokenError):
        return ()
    return tuple(values)


def iter_corpus_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for configured in paths:
        path = configured.resolve()
        candidates = [path] if path.is_file() else path.rglob("*.py")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen or resolved.suffix != ".py":
                continue
            try:
                relative = resolved.relative_to(PROJECT_ROOT)
            except ValueError:
                relative = resolved
            if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
                continue
            seen.add(resolved)
            yield resolved


def ngrams(values: tuple[str, ...], size: int) -> Iterable[tuple[str, ...]]:
    for index in range(len(values) - size + 1):
        yield values[index : index + size]


def build_corpus_index(
    paths: Iterable[Path], minimum_tokens: int
) -> tuple[dict[tuple[str, ...], dict[str, Any]], list[dict[str, Any]]]:
    index: dict[tuple[str, ...], dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    for path in sorted(iter_corpus_files(paths)):
        source = path.read_text(encoding="utf-8")
        values = source_tokens(source)
        display_path = (
            path.relative_to(PROJECT_ROOT).as_posix()
            if path.is_relative_to(PROJECT_ROOT)
            else str(path)
        )
        files.append(
            {
                "path": display_path,
                "sha256": file_sha256(path),
                "token_count": len(values),
            }
        )
        for offset, gram in enumerate(ngrams(values, minimum_tokens)):
            index.setdefault(
                gram,
                {
                    "path": display_path,
                    "token_offset": offset,
                },
            )
    return index, files


def inspect_dataset(
    archive_path: Path,
    member: str,
    corpus_index: dict[tuple[str, ...], dict[str, Any]],
    minimum_tokens: int,
    max_reported_matches: int,
) -> dict[str, Any]:
    record_count = 0
    eligible_code_count = 0
    unique_code_hashes: set[str] = set()
    provenance_error_count = 0
    code_hash_error_count = 0
    match_count = 0
    matches: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        with archive.open(member) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    record = json.loads(line)
                    record_count += 1
                    source = record.get("reference_code")
                    code_hash = record.get("code_hash")
                    if not isinstance(source, str) or not isinstance(code_hash, str):
                        provenance_error_count += 1
                        continue
                    if record.get("code_generator_version") is None or record.get("code_generator_seed") is None:
                        provenance_error_count += 1
                    actual_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
                    if actual_hash != code_hash:
                        code_hash_error_count += 1
                    if code_hash in unique_code_hashes:
                        continue
                    unique_code_hashes.add(code_hash)
                    values = source_tokens(source)
                    if len(values) < minimum_tokens:
                        continue
                    eligible_code_count += 1
                    found: tuple[tuple[str, ...], dict[str, Any], int] | None = None
                    for offset, gram in enumerate(ngrams(values, minimum_tokens)):
                        corpus_match = corpus_index.get(gram)
                        if corpus_match is not None:
                            found = (gram, corpus_match, offset)
                            break
                    if found is None:
                        continue
                    match_count += 1
                    if len(matches) < max_reported_matches:
                        gram, corpus_match, offset = found
                        matches.append(
                            {
                                "record_line": line_number,
                                "record_id": record.get("record_id"),
                                "code_id": record.get("code_id"),
                                "code_token_offset": offset,
                                "corpus_path": corpus_match["path"],
                                "corpus_token_offset": corpus_match["token_offset"],
                                "matched_tokens": list(gram),
                                "classification": "first_party_repository_match",
                            }
                        )
    return {
        "record_count": record_count,
        "unique_code_count": len(unique_code_hashes),
        "eligible_code_count": eligible_code_count,
        "match_count": match_count,
        "reported_match_count": len(matches),
        "provenance_error_count": provenance_error_count,
        "code_hash_error_count": code_hash_error_count,
        "matches": matches,
    }


def main() -> None:
    args = parse_args()
    if args.minimum_tokens < 8:
        raise ValueError("--minimum-tokensは8以上にしてください")
    if args.max_reported_matches < 0:
        raise ValueError("--max-reported-matchesは0以上にしてください")
    archive_path = args.dataset_archive.resolve()
    corpus_paths = args.corpus or [PROJECT_ROOT]
    corpus_index, corpus_files = build_corpus_index(corpus_paths, args.minimum_tokens)
    dataset = inspect_dataset(
        archive_path,
        args.dataset_member,
        corpus_index,
        args.minimum_tokens,
        args.max_reported_matches,
    )
    report = {
        "report_version": 1,
        "method": "exact_python_lexical_token_ngram",
        "minimum_match_tokens": args.minimum_tokens,
        "scope": {
            "statement": "明示した比較コーパスに対する完全一致検査であり、インターネット上の全コードとの非一致を保証しない。",
            "corpus_origin": "first_party_repository_source",
            "excluded_directories": sorted(EXCLUDED_DIRECTORY_NAMES),
        },
        "dataset": {
            "archive": archive_path.relative_to(PROJECT_ROOT).as_posix(),
            "archive_sha256": file_sha256(archive_path),
            "member": args.dataset_member,
            **dataset,
        },
        "corpus": {
            "file_count": len(corpus_files),
            "ngram_count": len(corpus_index),
            "files": corpus_files,
        },
    }
    if dataset["provenance_error_count"] or dataset["code_hash_error_count"]:
        raise ValueError("データセットのコード来歴またはhashに不整合があります")
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output_path), **dataset}, ensure_ascii=False, indent=2))
    if args.fail_on_match and dataset["match_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
