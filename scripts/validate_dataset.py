"""Validate the contract review dataset read-only and print statistics and its fingerprint."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = PROJECT_ROOT / "risk_labels.csv"
REVIEW_POINTS_PATH = PROJECT_ROOT / "contract_general_review_points.json"
CONTRACT_TEXTS_DIRECTORY = "contract_texts"
EXPECTED_CONTRACT_COUNT = 40
EXPECTED_REVIEW_POINT_COUNT = 20
CONTRACT_DIRECTORIES = (
    "Real Estate and Site Use",
    "Special-Purpose Agreements and Other",
    "Platform and Channel Partnerships",
    "Advertising and Marketing",
    "Technology and Intellectual Property",
    "Services and Engineering",
    "Goods and Equipment Transactions",
    "Finance and Asset Transactions",
)
METADATA_COLUMNS = (
    "ID",
    "Scenario",
    "Contract Name",
    "File Path",
    "Review Party",
    "Review Party Role",
    "Risk Count",
    "Matched Review Points",
)
RULE_COLUMN_PREFIX = "Rule_"
POSITIVE_LABEL = "Risk identified"
NEGATIVE_LABEL = "No risk identified"
HIT_SEPARATOR = "；"


def load_review_points(errors: list[str]) -> list[str]:
    try:
        points = json.loads(REVIEW_POINTS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Unable to read or parse the review points file: {exc}")
        return []

    if not isinstance(points, list):
        errors.append("The top level of the review points JSON must be an array.")
        return []
    if len(points) != EXPECTED_REVIEW_POINT_COUNT:
        errors.append(
            f"Expected {EXPECTED_REVIEW_POINT_COUNT} review points, found {len(points)}."
        )

    titles = []
    for index, point in enumerate(points, start=1):
        if not isinstance(point, dict):
            errors.append(f"Review point {index} must be an object.")
            continue
        for field in ("Review Point Title", "Review Point Description"):
            value = point.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"Review point {index} field '{field}' must be a non-empty string.")
        title = point.get("Review Point Title")
        if isinstance(title, str) and title.strip():
            if title != title.strip():
                errors.append(f"Review point {index} title has leading or trailing whitespace.")
            titles.append(title)
        if "Note" in point and not isinstance(point["Note"], str):
            errors.append(f"Review point {index} field 'Note' must be a string.")

    if len(titles) != len(set(titles)):
        errors.append("Duplicate review point titles found.")
    return titles


def load_labels(errors: list[str]) -> tuple[list[str], list[dict]]:
    try:
        with LABELS_PATH.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(f"Unable to read or parse the risk labels file: {exc}")
        return [], []
    return headers, rows


def parse_integer(value: str, field: str, location: str, errors: list[str]) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors.append(f"{location}: '{field}' must be an integer.")
        return None
    minimum = 1 if field == "ID" else 0
    if number < minimum:
        errors.append(f"{location}: '{field}' must be at least {minimum}.")
        return None
    return number


def validate_contract_path(row: dict, location: str, errors: list[str]) -> str | None:
    filename = row.get("File Path")
    if not isinstance(filename, str) or not filename.strip():
        return None
    relative = PurePosixPath(filename)
    if (
        relative.is_absolute()
        or "\\" in filename
        or ".." in relative.parts
        or len(relative.parts) != 3
        or relative.suffix != ".md"
        or filename != relative.as_posix()
    ):
        errors.append(
            f"{location}: File Path must be a normalized relative path in the format "
            "'contract_texts/<scenario>/<contract_name>.md'."
        )
        return None
    if relative.parts[0] != CONTRACT_TEXTS_DIRECTORY:
        errors.append(f"{location}: File Path must be located in the {CONTRACT_TEXTS_DIRECTORY} directory.")
        return None
    if relative.parts[1] not in CONTRACT_DIRECTORIES:
        errors.append(f"{location}: File Path references an unconfigured scenario directory.")
        return None
    if row.get("Scenario") != relative.parts[1]:
        errors.append(f"{location}: Scenario does not match the directory in File Path.")

    path = PROJECT_ROOT / filename
    if not path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
        errors.append(f"{location}: Contract path is outside the project directory.")
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{location}: Contract text is empty: {filename}")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{location}: Unable to read contract as UTF-8: {filename} ({exc})")
    return filename


def validate_labels(
    headers: list[str], rows: list[dict], titles: list[str], errors: list[str]
) -> Counter:
    rule_columns = [RULE_COLUMN_PREFIX + title for title in titles]
    expected_columns = set(METADATA_COLUMNS) | set(rule_columns)
    if len(headers) != len(set(headers)):
        errors.append("Duplicate CSV headers found.")
    missing = expected_columns - set(headers)
    extra = set(headers) - expected_columns
    if missing:
        errors.append(f"Missing CSV columns: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"Unexpected CSV columns: {', '.join(sorted(extra))}")
    if len(rows) != EXPECTED_CONTRACT_COUNT:
        errors.append(f"Expected {EXPECTED_CONTRACT_COUNT} contracts, found {len(rows)}.")

    seen_ids = set()
    seen_paths = set()
    positive_counts = Counter({title: 0 for title in titles})
    for index, row in enumerate(rows, start=1):
        location = f"Contract record {index}"
        if None in row or any(value is None for value in row.values()):
            errors.append(f"{location}: Field count does not match the CSV headers.")
        for field in METADATA_COLUMNS:
            if field == "Matched Review Points":
                continue
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{location}: '{field}' is empty or missing.")

        contract_id = parse_integer(row.get("ID"), "ID", location, errors)
        if contract_id is not None:
            if contract_id in seen_ids:
                errors.append(f"{location}: Duplicate ID: {contract_id}")
            seen_ids.add(contract_id)
        filename = validate_contract_path(row, location, errors)
        if filename is not None:
            if filename in seen_paths:
                errors.append(f"{location}: Duplicate contract path: {filename}")
            seen_paths.add(filename)

        positives = set()
        for title, column in zip(titles, rule_columns):
            value = row.get(column)
            if value not in (POSITIVE_LABEL, NEGATIVE_LABEL):
                errors.append(
                    f"{location}: '{column}' must be '{POSITIVE_LABEL}' or '{NEGATIVE_LABEL}'."
                )
            elif value == POSITIVE_LABEL:
                positives.add(title)
                positive_counts[title] += 1

        risk_count = parse_integer(row.get("Risk Count"), "Risk Count", location, errors)
        if risk_count is not None and risk_count != len(positives):
            errors.append(
                f"{location}: Risk Count is {risk_count}, but {len(positives)} review points have positive labels."
            )
        raw_hits = row.get("Matched Review Points")
        if not isinstance(raw_hits, str):
            errors.append(f"{location}: 'Matched Review Points' is missing.")
            continue
        hits = [] if not raw_hits.strip() else [part.strip() for part in raw_hits.split(HIT_SEPARATOR)]
        if len(hits) != len(set(hits)):
            errors.append(f"{location}: Duplicate entries in Matched Review Points.")
        if set(hits) != positives:
            errors.append(f"{location}: Matched Review Points does not match the positive label columns.")

    inventory = set()
    for directory in CONTRACT_DIRECTORIES:
        category_path = PROJECT_ROOT / CONTRACT_TEXTS_DIRECTORY / directory
        if not category_path.is_dir():
            errors.append(f"Missing scenario directory: {directory}")
            continue
        inventory.update(path.relative_to(PROJECT_ROOT).as_posix() for path in category_path.rglob("*.md"))
    for filename in sorted(inventory - seen_paths):
        errors.append(f"Contract file is not registered in the CSV: {filename}")
    return positive_counts


def dataset_fingerprint() -> str:
    sources = [LABELS_PATH, REVIEW_POINTS_PATH]
    for directory in CONTRACT_DIRECTORIES:
        sources.extend((PROJECT_ROOT / CONTRACT_TEXTS_DIRECTORY / directory).rglob("*.md"))
    digest = hashlib.sha256()
    for path in sorted(sources, key=lambda item: item.relative_to(PROJECT_ROOT).as_posix()):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def print_statistics(rows: list[dict], titles: list[str], positive_counts: Counter) -> None:
    category_counts = Counter(row["Scenario"] for row in rows)
    risk_counts = [int(row["Risk Count"]) for row in rows]
    positives = sum(positive_counts.values())
    decisions = len(rows) * len(titles)
    zero_risk = sum(count == 0 for count in risk_counts)
    print("\nDataset Overview")
    print(f"Contracts: {len(rows)}; Scenarios: {len(category_counts)}; Review points: {len(titles)}")
    print(
        f"Contract-review-point decisions: {decisions}; "
        f"Positive labels: {positives}; Negative labels: {decisions - positives}"
    )
    print(
        f"Contracts with positive labels: {len(rows) - zero_risk}; "
        f"Contracts with only negative labels: {zero_risk}"
    )
    if decisions:
        print(
            f"Positive-label rate: {positives / decisions:.2%}; "
            f"Decision-level accuracy when predicting no risk for all: {1 - positives / decisions:.2%}"
        )
    print(f"Positive labels per contract: {min(risk_counts, default=0)}–{max(risk_counts, default=0)}")
    print("\nBy scenario (contracts / positive labels)")
    category_positives = Counter()
    for row in rows:
        category_positives[row["Scenario"]] += int(row["Risk Count"])
    for category in CONTRACT_DIRECTORIES:
        print(f"  {category}: {category_counts[category]} / {category_positives[category]}")
    print("\nBy review point (positive labels / negative labels)")
    for title in titles:
        count = positive_counts[title]
        print(f"  {title}: {count} / {len(rows) - count}")


def main() -> int:
    errors = []
    titles = load_review_points(errors)
    headers, rows = load_labels(errors)
    positive_counts = validate_labels(headers, rows, titles, errors)
    if errors:
        print(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    try:
        fingerprint = dataset_fingerprint()
    except OSError as exc:
        print(f"Validation failed: unable to calculate the dataset fingerprint: {exc}")
        return 1
    print("Structure and consistency validation passed.")
    print_statistics(rows, titles, positive_counts)
    print(f"\nDataset fingerprint (SHA-256): {fingerprint}")
    print(
        "This validation does not verify the legal accuracy of labels, "
        "the adequacy of de-identification, or authorization for publication."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
