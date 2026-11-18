# Contract Review Dataset

A contract risk identification benchmark for a designated party, intended for paper reproduction and method comparison. The data is based on real contracts that have been de-identified or adapted. This repository provides a sample of the full dataset.

- 40 English Markdown contracts across 8 business categories, with 5 contracts per category.
- 20 review points, including their scope, triggering conditions, and exemptions.
- A designated review party for each contract, with 800 contract-review-point binary labels: 130 `Risk identified` and 670 `No risk identified`.
- 32 contracts with at least one positive label and 8 contracts with only negative labels.

## 📊 Data Description

`Risk identified` means that the contract triggers the corresponding review point from the designated party's perspective. The dataset provides only contract-level binary labels, without evidence spans, item-level explanations, or severity annotations.

| Scenario | Contracts | Positive Labels |
| --- | ---: | ---: |
| Real Estate and Site Use | 5 | 18 |
| Special-Purpose Agreements and Other | 5 | 13 |
| Platform and Channel Partnerships | 5 | 16 |
| Advertising and Marketing | 5 | 21 |
| Technology and Intellectual Property | 5 | 21 |
| Services and Engineering | 5 | 19 |
| Goods and Equipment Transactions | 5 | 11 |
| Finance and Asset Transactions | 5 | 11 |

## 📁 Directory Structure and Data Format

```text
.
├── README.md                              # English documentation
├── contract_general_review_points.json    # 20 review rules
├── risk_labels.csv                        # Contract metadata and labels
├── contract_texts/                        # 8 category directories, 5 contracts each
└── scripts/validate_dataset.py            # Local validation script
```

Data files use UTF-8 encoding. Use `utf-8-sig` when reading the CSV to handle a possible BOM. Since fields may contain commas, use a standard CSV parser. Some texts are orders or confirmations that may refer to master agreements not included here, and attachments may be omitted. Do not automatically correct textual discrepancies, as they may correspond to risk labels.

### Review Rules JSON

Each object contains:

| Field | Description |
| --- | --- |
| `Review Point Title` | Unique review point identifier |
| `Review Point Description` | Scope, decision steps, triggering conditions, and exemptions |
| `Note` | Optional configuration notes |

The `Specified Entity Wording` placeholder in `Prohibition of external publication` must be configured by users; no specific keyword is provided. Some rules involve contextual information such as corporate group relationships, which must not be inferred or fabricated when absent from the data.

### Label CSV

Each row represents one contract and contains 28 columns: 8 metadata or summary fields and 20 review label fields. Label columns are named `Rule_<Review Point Title>` and contain either `Risk identified` or `No risk identified`.

| Field | Description |
| --- | --- |
| `ID` | Unique sample ID, currently 1–40 |
| `Scenario` | Business scenario, matching the category directory in the file path |
| `Contract Name` | Contract name, matching the filename without the `.md` extension |
| `File Path` | Relative contract path in the format `contract_texts/<scenario>/<contract_name>.md` |
| `Review Party`, `Review Party Role` | The party whose interests are being reviewed and its role; both are model inputs |
| `Risk Count` | Number of `Risk identified` labels, ranging from 0 to 7 |
| `Matched Review Points` | Positive review point titles separated by full-width semicolons (`；`); empty if none |

## 🚀 Loading the Data

The following example runs from the repository root and uses only the Python standard library:

```python
import csv
import json
from pathlib import Path

root = Path.cwd()
review_points = json.loads(
    (root / "contract_general_review_points.json").read_text(encoding="utf-8")
)
with (root / "risk_labels.csv").open(encoding="utf-8-sig", newline="") as source:
    record = next(csv.DictReader(source))

sample = {
    "contract_text": (root / record["File Path"]).read_text(encoding="utf-8"),
    "review_party": record["Review Party"],
    "review_party_role": record["Review Party Role"],
    "review_points": review_points,
}
reference_labels = {
    point["Review Point Title"]: int(record[f"Rule_{point['Review Point Title']}"] == "Risk identified")
    for point in review_points
}
```

Model inputs consist of the contract text, designated party, and review rules. Do not include `Risk Count`, `Matched Review Points`, or any reference labels in the input. Record missing or unparseable outputs as failures instead of silently assigning negative labels.

## ✅ Local Validation

Python 3.10+ and `uv` are required. No third-party Python dependencies are needed. Run from the repository root:

```bash
uv run scripts/validate_dataset.py
```

The read-only script checks fields, paths, file associations, rule-label consistency, and the consistency of `Risk Count` and `Matched Review Points`. It returns `0` on success and prints statistics and a SHA-256 data fingerprint; it returns `1` on failure. It does not modify files or call external APIs. It does not verify the legal correctness of labels, adequacy of de-identification, or authorization for publication.

Current data fingerprint:

```text
7c8b78b0a0441f8d1477d680a35e126c9a387c5888e5488b33352b7c97fd2b15
```

## 📜 License

This dataset is provided for academic research purposes only. The code in this repository is released under the MIT License. See the LICENSE file for details.
