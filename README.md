# Contract Review Dataset

[中文版](README_zh.md)

A contract risk identification benchmark for a designated party, intended for paper reproduction and method comparison. The data is based on real contracts that have been de-identified or adapted. This repository provides a sample of the full dataset.

- 40 Markdown contracts across 8 business categories, with 5 contracts per category, including Chinese, English, and bilingual Chinese-English texts.
- 20 review points, including their scope, triggering conditions, and exemptions.
- A designated review party for each contract, with 800 contract-review-point binary labels: 130 `有风险` (risk identified) and 670 `无风险` (no risk identified).
- 32 contracts with at least one positive label and 8 contracts with only negative labels.

## 📊 Data Description

`有风险` means that the contract triggers the corresponding review point from the designated party's perspective. The dataset provides only contract-level binary labels, without evidence spans, item-level explanations, or severity annotations.

| Business Category | Contracts | Positive Labels |
| --- | ---: | ---: |
| Real Estate and Premises Use (`不动产与场地使用`) | 5 | 18 |
| Special-purpose Agreements and Other (`专项协议与其他`) | 5 | 13 |
| Platform and Channel Partnerships (`平台与渠道合作`) | 5 | 16 |
| Advertising and Marketing (`广告与营销推广`) | 5 | 21 |
| Technology and Intellectual Property (`技术与知识产权`) | 5 | 21 |
| Services and Engineering (`服务与工程`) | 5 | 19 |
| Goods and Equipment Transactions (`货物与设备交易`) | 5 | 11 |
| Finance and Asset Transactions (`金融与资产交易`) | 5 | 11 |

## 📁 Directory Structure and Data Format

```text
.
├── README.md                              # English documentation
├── README_zh.md                           # Chinese documentation
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
| `审查点标题` | Unique review point identifier |
| `审查点描述` | Scope, decision steps, triggering conditions, and exemptions |
| `备注` | Optional configuration notes |

The asterisks in `保密条款*` and `争议解决*` are part of the titles. The `指定主体字样` placeholder in `禁止对外发布条款` must be configured by users; no specific keyword is provided. Some rules involve contextual information such as corporate group relationships, which must not be inferred or fabricated when absent from the data.

### Label CSV

Each row represents one contract and contains 28 columns: 8 metadata or summary fields and 20 review label fields. Label columns are named `规则_<审查点标题>` and contain either `有风险` or `无风险`.

| Field | Description |
| --- | --- |
| `序号` | Unique sample ID, currently 1–40 |
| `标的大类` | Business category, matching the category directory in the file path |
| `合同名` | Display name; it need not exactly match the filename or contract title |
| `文件名` | Relative contract path in the format `contract_texts/<category>/<contract_name>.md` |
| `立场方`, `立场方角色` | The party whose interests are being reviewed and its role; both are model inputs |
| `风险条数` | Number of `有风险` labels, ranging from 0 to 7 |
| `命中审查点` | Positive review point titles separated by Chinese semicolons (`；`); empty if none |

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
    "contract_text": (root / record["文件名"]).read_text(encoding="utf-8"),
    "review_party": record["立场方"],
    "review_party_role": record["立场方角色"],
    "review_points": review_points,
}
reference_labels = {
    point["审查点标题"]: int(record[f"规则_{point['审查点标题']}"] == "有风险")
    for point in review_points
}
```

Model inputs consist of the contract text, designated party, and review rules. Do not include `风险条数`, `命中审查点`, or any reference labels in the input. Record missing or unparseable outputs as failures instead of silently assigning negative labels.

## ✅ Local Validation

Python 3.10+ and `uv` are required. No third-party Python dependencies are needed. Run from the repository root:

```bash
uv run scripts/validate_dataset.py
```

The read-only script checks fields, paths, file associations, rule-label consistency, and the consistency of `风险条数` and `命中审查点`. It returns `0` on success and prints statistics and a SHA-256 data fingerprint; it returns `1` on failure. It does not modify files or call external APIs. It does not verify the legal correctness of labels, adequacy of de-identification, or authorization for publication.

Current data fingerprint:

```text
6ea9b684ee31c42c460a611ddbcf547b8ed62b2a9f9c459ebd9265305cd12de1
```

## 📜 License

This dataset is provided for academic research purposes only. The code in this repository is released under the MIT License. See the LICENSE file for details.
