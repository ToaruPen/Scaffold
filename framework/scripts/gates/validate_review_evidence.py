#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple


class _Context(NamedTuple):
    request_id: str
    scope_id: str
    run_id: str
    artifact_path: str
    expected_head: str
    expected_base: str | None
    review_head: str
    review_base: str | None
    review_artifact: str
    findings: list[object]


class _Policy(NamedTuple):
    fail_on_classifications: set[str]
    fail_on_unmapped_severity: set[str]


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": False,
        "provider": "review_engine",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to read input JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def _require_text(obj: dict[str, Any], key: str, parent: str = "") -> str:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"missing or invalid string: {prefix}{key}")
    return raw.strip()


def _optional_text(obj: dict[str, Any], key: str, parent: str = "") -> str | None:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid string: {prefix}{key}")
    return raw.strip()


def _require_object(obj: dict[str, Any], key: str, parent: str = "") -> dict[str, Any]:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, dict):
        raise ValueError(f"missing or invalid object: {prefix}{key}")
    return raw


def _require_list(obj: dict[str, Any], key: str, parent: str = "") -> list[object]:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, list):
        raise ValueError(f"missing or invalid array: {prefix}{key}")
    return raw


def _default_policy_path() -> Path:
    return Path("framework/config/review-evidence-policy.yaml")


def _default_policy() -> _Policy:
    return _Policy(
        fail_on_classifications={"stale", "schema_invalid"},
        fail_on_unmapped_severity={"P0", "P1"},
    )


def _parse_policy_yaml(text: str) -> dict[str, list[str]]:
    in_rerun = False
    active_list: str | None = None
    result: dict[str, list[str]] = {
        "fail_on_classifications": [],
        "fail_on_unmapped_severity": [],
    }

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line == "rerun:":
            in_rerun = True
            active_list = None
            continue
        if not in_rerun:
            raise ValueError("policy must start with top-level 'rerun:' block")
        if line == "  fail_on_classifications:":
            active_list = "fail_on_classifications"
            continue
        if line == "  fail_on_unmapped_severity:":
            active_list = "fail_on_unmapped_severity"
            continue
        if line.startswith("    - ") and active_list is not None:
            value = line[6:].strip()
            if not value:
                raise ValueError("policy list item must not be empty")
            result[active_list].append(value)
            continue
        raise ValueError(f"unsupported policy yaml line: {raw_line}")
    return result


def _normalize_policy(raw: dict[str, list[str]]) -> _Policy:
    defaults = _default_policy()
    raw_classes = raw.get("fail_on_classifications")
    raw_severity = raw.get("fail_on_unmapped_severity")
    if raw_classes is None:
        raw_classes = sorted(defaults.fail_on_classifications)
    if raw_severity is None:
        raw_severity = sorted(defaults.fail_on_unmapped_severity)

    allowed_classes = {"stale", "schema_invalid"}
    allowed_severity = {"P0", "P1", "P2", "P3"}

    if any(value not in allowed_classes for value in raw_classes):
        raise ValueError("unsupported fail_on_classifications value")
    if any(value not in allowed_severity for value in raw_severity):
        raise ValueError("unsupported fail_on_unmapped_severity value")

    return _Policy(
        fail_on_classifications=set(raw_classes),
        fail_on_unmapped_severity=set(raw_severity),
    )


def _load_policy(policy_path: Path | None) -> tuple[_Policy, str]:
    path = policy_path if policy_path is not None else _default_policy_path()
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"failed to read policy yaml: {exc}") from exc
    return _normalize_policy(_parse_policy_yaml(text)), str(path)


def _empty_counts() -> dict[str, int]:
    return {
        "verified": 0,
        "stale": 0,
        "unmapped": 0,
        "schema_invalid": 0,
    }


def _empty_unmapped_severity_counts() -> dict[str, int]:
    return {
        "P0": 0,
        "P1": 0,
        "P2": 0,
        "P3": 0,
        "unknown": 0,
    }


def _safe_relative_path(path_text: str) -> bool:
    path = PurePosixPath(path_text)
    if path.is_absolute():
        return False
    return ".." not in path.parts


def _snippet_in_window(lines: list[str], snippet: str, start_line: int, end_line: int) -> bool:
    if end_line > len(lines):
        return False
    snippet_norm = snippet.strip()
    if not snippet_norm:
        return False

    exact_text = "\n".join(lines[start_line - 1 : end_line])
    if snippet_norm in exact_text:
        return True

    expanded_start = max(1, start_line - 5)
    expanded_end = min(len(lines), end_line + 5)
    nearby_text = "\n".join(lines[expanded_start - 1 : expanded_end])
    return snippet_norm in nearby_text


def _schema_invalid_check(index: int, reason: str) -> dict[str, Any]:
    return {
        "index": index,
        "finding_id": f"index-{index}",
        "severity": "unknown",
        "classification": "schema_invalid",
        "reasons": [reason],
    }


def _required_finding_fields(
    finding: dict[str, Any], index: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    finding_id_raw = finding.get("finding_id")
    finding_id = finding_id_raw.strip() if isinstance(finding_id_raw, str) else f"index-{index}"

    severity_raw = finding.get("severity")
    severity = severity_raw if isinstance(severity_raw, str) else "unknown"

    path_raw = finding.get("path")
    path = path_raw.strip() if isinstance(path_raw, str) else ""
    start_line = finding.get("start_line")
    end_line = finding.get("end_line")
    snippet_raw = finding.get("snippet")
    snippet = snippet_raw if isinstance(snippet_raw, str) else ""

    has_valid_start = isinstance(start_line, int) and start_line >= 1
    has_valid_end = isinstance(end_line, int) and end_line >= 1
    line_range_invalid = (
        isinstance(start_line, int)
        and isinstance(end_line, int)
        and start_line >= 1
        and end_line >= 1
        and end_line < start_line
    )

    checks = [
        (not finding_id, "finding_id_missing_or_invalid"),
        (severity not in {"P0", "P1", "P2", "P3"}, "severity_missing_or_invalid"),
        (not path, "path_missing_or_invalid"),
        (not has_valid_start, "start_line_missing_or_invalid"),
        (not has_valid_end, "end_line_missing_or_invalid"),
        (line_range_invalid, "line_range_invalid"),
        (not snippet.strip(), "snippet_missing_or_invalid"),
    ]

    reasons = [reason for failed, reason in checks if failed]
    if reasons:
        error: dict[str, Any] = {
            "index": index,
            "finding_id": finding_id,
            "severity": severity if severity in {"P0", "P1", "P2", "P3"} else "unknown",
            "classification": "schema_invalid",
            "reasons": reasons,
        }
        if path:
            error["path"] = path
        if isinstance(start_line, int):
            error["start_line"] = start_line
        if isinstance(end_line, int):
            error["end_line"] = end_line
        return None, error

    normalized = {
        "finding_id": finding_id,
        "severity": severity,
        "path": path,
        "start_line": start_line,
        "end_line": end_line,
        "snippet": snippet,
    }
    return normalized, None


def _classify_location(normalized: dict[str, Any], repo_root: Path) -> tuple[str, list[str]]:
    path = normalized["path"]
    start_line = normalized["start_line"]
    end_line = normalized["end_line"]
    snippet = normalized["snippet"]

    if not _safe_relative_path(path):
        return "schema_invalid", ["path_not_safe_relative"]

    source_path = (repo_root / path).resolve()
    if not source_path.exists() or not source_path.is_file():
        return "unmapped", ["path_not_found"]

    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return "unmapped", ["path_not_readable"]

    if end_line > len(lines):
        return "unmapped", ["line_range_out_of_bounds"]
    if not _snippet_in_window(lines, snippet, start_line, end_line):
        return "unmapped", ["snippet_not_found_near_range"]
    return "verified", []


def _classify_finding(
    *,
    finding: object,
    index: int,
    stale: bool,
    repo_root: Path,
) -> dict[str, Any]:
    if not isinstance(finding, dict):
        return _schema_invalid_check(index, "finding_not_object")

    normalized, error = _required_finding_fields(finding, index)
    if error is not None:
        return error
    assert normalized is not None

    classification = "stale" if stale else "verified"
    reasons = ["review_sha_mismatch"] if stale else []
    if not stale:
        classification, reasons = _classify_location(normalized, repo_root)

    return {
        "index": index,
        "finding_id": normalized["finding_id"],
        "severity": normalized["severity"],
        "classification": classification,
        "path": normalized["path"],
        "start_line": normalized["start_line"],
        "end_line": normalized["end_line"],
        "reasons": reasons,
    }


def _parse_context(payload: dict[str, Any]) -> _Context:
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

    expected = _require_object(payload, "expected")
    expected_head = _require_text(expected, "head_sha", "expected")
    expected_base = _optional_text(expected, "base_sha", "expected")

    review = _require_object(payload, "review")
    evidence = _require_object(review, "evidence", "review")
    findings = _require_list(review, "findings", "review")

    review_head = _require_text(evidence, "head_sha", "review.evidence")
    review_base = _optional_text(evidence, "base_sha", "review.evidence")
    review_artifact = _require_text(evidence, "artifact_path", "review.evidence")

    return _Context(
        request_id=request_id,
        scope_id=scope_id,
        run_id=run_id,
        artifact_path=artifact_path,
        expected_head=expected_head,
        expected_base=expected_base,
        review_head=review_head,
        review_base=review_base,
        review_artifact=review_artifact,
        findings=findings,
    )


def _sha_mismatch_reasons(context: _Context) -> list[str]:
    reasons: list[str] = []
    if context.expected_head != context.review_head:
        reasons.append("head_sha_mismatch")
    if context.expected_base is not None:
        if context.review_base is None:
            reasons.append("base_sha_missing")
        elif context.review_base != context.expected_base:
            reasons.append("base_sha_mismatch")
    return reasons


def _evaluate_findings(
    *,
    findings: list[object],
    stale: bool,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int], int]:
    checks: list[dict[str, Any]] = []
    counts = _empty_counts()
    unmapped_by_severity = _empty_unmapped_severity_counts()
    schema_invalid_count = 0

    for index, finding in enumerate(findings):
        check = _classify_finding(finding=finding, index=index, stale=stale, repo_root=repo_root)
        checks.append(check)

        classification = check["classification"]
        counts[classification] += 1

        if classification == "schema_invalid":
            schema_invalid_count += 1
            continue
        if classification != "unmapped":
            continue

        severity = check.get("severity")
        key = (
            severity
            if isinstance(severity, str) and severity in {"P0", "P1", "P2", "P3"}
            else "unknown"
        )
        unmapped_by_severity[key] += 1

    return checks, counts, unmapped_by_severity, schema_invalid_count


def _build_decision(
    *,
    policy: _Policy,
    sha_reasons: list[str],
    schema_invalid_count: int,
    unmapped_by_severity: dict[str, int],
    checks: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    mismatch_reasons: list[str] = []
    warnings: list[str] = []

    if sha_reasons:
        if "stale" in policy.fail_on_classifications:
            mismatch_reasons.extend(sha_reasons)
        else:
            warnings.append("stale_evidence_non_blocking")

    if schema_invalid_count > 0:
        if "schema_invalid" in policy.fail_on_classifications:
            mismatch_reasons.append("schema_invalid_finding_present")
        else:
            warnings.append("schema_invalid_finding_non_blocking")

    blocking_unmapped = sum(
        unmapped_by_severity.get(severity, 0) for severity in policy.fail_on_unmapped_severity
    )
    if blocking_unmapped > 0:
        mismatch_reasons.append("unmapped_required_severity_finding_present")

    for check in checks:
        if check.get("classification") != "unmapped":
            continue
        severity = check.get("severity", "unknown")
        if not isinstance(severity, str) or severity in policy.fail_on_unmapped_severity:
            continue
        finding_id = check.get("finding_id", f"index-{check.get('index', 'unknown')}")
        warnings.append(f"unmapped_non_blocking:{severity}:{finding_id}")

    return mismatch_reasons, warnings


def _policy_to_result(policy: _Policy) -> dict[str, list[str]]:
    return {
        "fail_on_classifications": sorted(policy.fail_on_classifications),
        "fail_on_unmapped_severity": sorted(policy.fail_on_unmapped_severity),
    }


def _build_result(
    payload: dict[str, Any], repo_root: Path, policy: _Policy, policy_path: str
) -> tuple[dict[str, Any], bool]:
    context = _parse_context(payload)
    sha_reasons = _sha_mismatch_reasons(context)
    checks, counts, unmapped_by_severity, schema_invalid_count = _evaluate_findings(
        findings=context.findings,
        stale=bool(sha_reasons),
        repo_root=repo_root,
    )
    mismatch_reasons, warnings = _build_decision(
        policy=policy,
        sha_reasons=sha_reasons,
        schema_invalid_count=schema_invalid_count,
        unmapped_by_severity=unmapped_by_severity,
        checks=checks,
    )

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "stage": "review-evidence-link",
        "status": "pass" if passed else "fail",
        "artifact_path": context.artifact_path,
        "review_artifact_path": context.review_artifact,
        "head_sha": context.expected_head,
        "review_head_sha": context.review_head,
        "policy_path": policy_path,
        "policy": _policy_to_result(policy),
        "mismatch_reasons": mismatch_reasons,
        "classification_counts": counts,
        "finding_checks": checks,
    }
    if context.expected_base is not None:
        result["base_sha"] = context.expected_base
    if context.review_base is not None:
        result["review_base_sha"] = context.review_base
    if warnings:
        result["warnings"] = warnings
    if not passed:
        result["errors"] = [_error("E_PROVIDER_FAILURE", "review evidence link check failed")]
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review evidence link contract")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", help="Path to write result JSON")
    parser.add_argument("--policy", help="Path to review evidence policy YAML")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None

    try:
        payload = _read_json(Path(args.input))
        policy, policy_path = _load_policy(Path(args.policy) if args.policy else None)
        result, passed = _build_result(payload, Path.cwd(), policy, policy_path)
        exit_code = 0 if passed else 2
    except ValueError as exc:
        result = {
            "request_id": "unknown",
            "scope_id": "unknown",
            "run_id": "unknown",
            "stage": "review-evidence-link",
            "status": "fail",
            "artifact_path": "unknown",
            "review_artifact_path": "unknown",
            "head_sha": "unknown",
            "policy_path": str(_default_policy_path()),
            "policy": _policy_to_result(_default_policy()),
            "mismatch_reasons": ["invalid_input"],
            "classification_counts": _empty_counts(),
            "finding_checks": [],
            "errors": [_error("E_INPUT_INVALID", str(exc))],
        }
        exit_code = 2

    output_text = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    print(output_text, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
