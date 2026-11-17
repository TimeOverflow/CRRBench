"""只读校验合同审查数据集，并在终端输出统计信息与数据指纹。"""

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
    "不动产与场地使用",
    "专项协议与其他",
    "平台与渠道合作",
    "广告与营销推广",
    "技术与知识产权",
    "服务与工程",
    "货物与设备交易",
    "金融与资产交易",
)
METADATA_COLUMNS = (
    "序号",
    "标的大类",
    "合同名",
    "文件名",
    "立场方",
    "立场方角色",
    "风险条数",
    "命中审查点",
)
RULE_COLUMN_PREFIX = "规则_"
POSITIVE_LABEL = "有风险"
NEGATIVE_LABEL = "无风险"
HIT_SEPARATOR = "；"


def load_review_points(errors: list[str]) -> list[str]:
    try:
        points = json.loads(REVIEW_POINTS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"审查规则文件无法读取或解析：{exc}")
        return []

    if not isinstance(points, list):
        errors.append("审查规则 JSON 的顶层必须是数组。")
        return []
    if len(points) != EXPECTED_REVIEW_POINT_COUNT:
        errors.append(
            f"审查规则应有 {EXPECTED_REVIEW_POINT_COUNT} 个，实际为 {len(points)} 个。"
        )

    titles = []
    for index, point in enumerate(points, start=1):
        if not isinstance(point, dict):
            errors.append(f"第 {index} 个审查规则不是对象。")
            continue
        for field in ("审查点标题", "审查点描述"):
            value = point.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"第 {index} 个审查规则的“{field}”必须是非空字符串。")
        title = point.get("审查点标题")
        if isinstance(title, str) and title.strip():
            if title != title.strip():
                errors.append(f"第 {index} 个审查规则标题存在首尾空白。")
            titles.append(title)
        if "备注" in point and not isinstance(point["备注"], str):
            errors.append(f"第 {index} 个审查规则的“备注”必须是字符串。")

    if len(titles) != len(set(titles)):
        errors.append("审查规则标题存在重复。")
    return titles


def load_labels(errors: list[str]) -> tuple[list[str], list[dict]]:
    try:
        with LABELS_PATH.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(f"风险标签文件无法读取或解析：{exc}")
        return [], []
    return headers, rows


def parse_integer(value: str, field: str, location: str, errors: list[str]) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors.append(f"{location}的“{field}”不是整数。")
        return None
    minimum = 1 if field == "序号" else 0
    if number < minimum:
        errors.append(f"{location}的“{field}”必须不小于 {minimum}。")
        return None
    return number


def validate_contract_path(row: dict, location: str, errors: list[str]) -> str | None:
    filename = row.get("文件名")
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
        errors.append(f"{location}的文件名必须是规范的“contract_texts/类别/合同名.md”相对路径。")
        return None
    if relative.parts[0] != CONTRACT_TEXTS_DIRECTORY:
        errors.append(f"{location}的文件名必须位于 {CONTRACT_TEXTS_DIRECTORY} 目录。")
        return None
    if relative.parts[1] not in CONTRACT_DIRECTORIES:
        errors.append(f"{location}引用了未配置的合同类别目录。")
        return None
    if row.get("标的大类") != relative.parts[1]:
        errors.append(f"{location}的类别与文件名中的目录不一致。")

    path = PROJECT_ROOT / filename
    if not path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
        errors.append(f"{location}引用的合同路径超出项目目录。")
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{location}引用的合同文本为空：{filename}")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{location}引用的合同无法按 UTF-8 读取：{filename}（{exc}）")
    return filename


def validate_labels(
    headers: list[str], rows: list[dict], titles: list[str], errors: list[str]
) -> Counter:
    rule_columns = [RULE_COLUMN_PREFIX + title for title in titles]
    expected_columns = set(METADATA_COLUMNS) | set(rule_columns)
    if len(headers) != len(set(headers)):
        errors.append("CSV 表头存在重复列。")
    missing = expected_columns - set(headers)
    extra = set(headers) - expected_columns
    if missing:
        errors.append(f"CSV 缺少字段：{'、'.join(sorted(missing))}")
    if extra:
        errors.append(f"CSV 存在未定义字段：{'、'.join(sorted(extra))}")
    if len(rows) != EXPECTED_CONTRACT_COUNT:
        errors.append(f"CSV 应有 {EXPECTED_CONTRACT_COUNT} 份合同，实际为 {len(rows)} 份。")

    seen_ids = set()
    seen_paths = set()
    positive_counts = Counter({title: 0 for title in titles})
    for index, row in enumerate(rows, start=1):
        location = f"第 {index} 条合同记录"
        if None in row or any(value is None for value in row.values()):
            errors.append(f"{location}的字段数量与 CSV 表头不一致。")
        for field in METADATA_COLUMNS:
            if field == "命中审查点":
                continue
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{location}的“{field}”为空或缺失。")

        contract_id = parse_integer(row.get("序号"), "序号", location, errors)
        if contract_id is not None:
            if contract_id in seen_ids:
                errors.append(f"{location}的序号重复：{contract_id}")
            seen_ids.add(contract_id)
        filename = validate_contract_path(row, location, errors)
        if filename is not None:
            if filename in seen_paths:
                errors.append(f"{location}重复引用了合同文件：{filename}")
            seen_paths.add(filename)

        positives = set()
        for title, column in zip(titles, rule_columns):
            value = row.get(column)
            if value not in (POSITIVE_LABEL, NEGATIVE_LABEL):
                errors.append(f"{location}的“{column}”不是“有风险”或“无风险”。")
            elif value == POSITIVE_LABEL:
                positives.add(title)
                positive_counts[title] += 1

        risk_count = parse_integer(row.get("风险条数"), "风险条数", location, errors)
        if risk_count is not None and risk_count != len(positives):
            errors.append(
                f"{location}的风险条数为 {risk_count}，但正标签审查点数量为 {len(positives)}。"
            )
        raw_hits = row.get("命中审查点")
        if not isinstance(raw_hits, str):
            errors.append(f"{location}的“命中审查点”缺失。")
            continue
        hits = [] if not raw_hits.strip() else [part.strip() for part in raw_hits.split(HIT_SEPARATOR)]
        if len(hits) != len(set(hits)):
            errors.append(f"{location}的命中审查点存在重复。")
        if set(hits) != positives:
            errors.append(f"{location}的命中审查点与正标签列不一致。")

    inventory = set()
    for directory in CONTRACT_DIRECTORIES:
        category_path = PROJECT_ROOT / CONTRACT_TEXTS_DIRECTORY / directory
        if not category_path.is_dir():
            errors.append(f"缺少合同类别目录：{directory}")
            continue
        inventory.update(path.relative_to(PROJECT_ROOT).as_posix() for path in category_path.rglob("*.md"))
    for filename in sorted(inventory - seen_paths):
        errors.append(f"合同文件未在 CSV 中登记：{filename}")
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
    category_counts = Counter(row["标的大类"] for row in rows)
    risk_counts = [int(row["风险条数"]) for row in rows]
    positives = sum(positive_counts.values())
    decisions = len(rows) * len(titles)
    zero_risk = sum(count == 0 for count in risk_counts)
    print("\n数据概览")
    print(f"合同：{len(rows)} 份；类别：{len(category_counts)} 个；审查点：{len(titles)} 个")
    print(f"合同—审查点判断：{decisions} 个；正标签：{positives} 个；负标签：{decisions - positives} 个")
    print(f"含正标签合同：{len(rows) - zero_risk} 份；全负标签合同：{zero_risk} 份")
    if decisions:
        print(f"正标签占比：{positives / decisions:.2%}；全部预测无风险的判断级 Accuracy：{1 - positives / decisions:.2%}")
    print(f"每份合同正标签数量范围：{min(risk_counts, default=0)}—{max(risk_counts, default=0)}")
    print("\n按类别统计（合同数 / 正标签数）")
    category_positives = Counter()
    for row in rows:
        category_positives[row["标的大类"]] += int(row["风险条数"])
    for category in CONTRACT_DIRECTORIES:
        print(f"  {category}：{category_counts[category]} / {category_positives[category]}")
    print("\n按审查点统计（正标签数 / 负标签数）")
    for title in titles:
        count = positive_counts[title]
        print(f"  {title}：{count} / {len(rows) - count}")


def main() -> int:
    errors = []
    titles = load_review_points(errors)
    headers, rows = load_labels(errors)
    positive_counts = validate_labels(headers, rows, titles, errors)
    if errors:
        print(f"校验失败，共 {len(errors)} 项错误：")
        for error in errors:
            print(f"  - {error}")
        return 1
    try:
        fingerprint = dataset_fingerprint()
    except OSError as exc:
        print(f"校验失败，无法计算数据指纹：{exc}")
        return 1
    print("结构与一致性校验通过。")
    print_statistics(rows, titles, positive_counts)
    print(f"\n数据指纹（SHA-256）：{fingerprint}")
    print("此校验不代表标签法律正确、脱敏充分或已获得公开许可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
