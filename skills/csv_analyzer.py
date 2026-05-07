SKILL_NAME = "csv_analyzer"
SKILL_DESCRIPTION = "Analyse, filtre et exporte des fichiers CSV - optimisé pour données e-commerce"
SKILL_VERSION = "1.0.0"

import csv
import json
from pathlib import Path


def run(action, **kwargs):
    try:
        action_name = str(action or "").strip().lower()

        if action_name == "analyze":
            return _analyze(kwargs.get("path"))

        if action_name == "filter":
            return _filter(
                kwargs.get("path"),
                kwargs.get("column"),
                kwargs.get("value"),
                kwargs.get("operator"),
            )

        if action_name == "sort":
            return _sort(
                kwargs.get("path"),
                kwargs.get("column"),
                kwargs.get("order", "asc"),
            )

        if action_name == "export":
            return _export(
                kwargs.get("path"),
                kwargs.get("output"),
                kwargs.get("format"),
                kwargs.get("filter_column"),
                kwargs.get("filter_value"),
            )

        if action_name == "summary":
            return _summary(kwargs.get("path"))

        return _error(f"Action inconnue: {action}")
    except Exception as error:
        return _error(str(error))


def _analyze(path):
    rows, columns = _read_csv(path)
    stats = _build_stats(rows, columns)

    return {
        "success": True,
        "data": rows[:5],
        "count": len(rows),
        "stats": stats,
        "error": "",
    }


def _filter(path, column, value, operator):
    rows, columns = _read_csv(path)

    if column not in columns:
        return _error(f"Colonne introuvable: {column}")

    operator = str(operator or "equals").lower()

    if operator not in {"equals", "contains", "gt", "lt"}:
        return _error(f"Operateur invalide: {operator}")

    filtered = [row for row in rows if _matches(row.get(column, ""), value, operator)]

    return {
        "success": True,
        "data": filtered,
        "count": len(filtered),
        "stats": {
            "column": column,
            "operator": operator,
            "value": value,
        },
        "error": "",
    }


def _sort(path, column, order):
    rows, columns = _read_csv(path)

    if column not in columns:
        return _error(f"Colonne introuvable: {column}")

    order = str(order or "asc").lower()

    if order not in {"asc", "desc"}:
        return _error(f"Ordre invalide: {order}")

    sorted_rows = sorted(
        rows,
        key=lambda row: _sort_value(row.get(column, "")),
        reverse=order == "desc",
    )

    return {
        "success": True,
        "data": sorted_rows,
        "count": len(sorted_rows),
        "stats": {
            "column": column,
            "order": order,
        },
        "error": "",
    }


def _export(path, output, output_format, filter_column, filter_value):
    rows, columns = _read_csv(path)

    if filter_column:
        if filter_column not in columns:
            return _error(f"Colonne introuvable: {filter_column}")

        rows = [row for row in rows if _matches(row.get(filter_column, ""), filter_value, "equals")]

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_format = str(output_format or "").lower()

    if output_format == "json":
        output_path.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    elif output_format == "csv":
        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    else:
        return _error(f"Format invalide: {output_format}")

    return {
        "success": True,
        "data": str(output_path),
        "count": len(rows),
        "stats": {
            "format": output_format,
            "filter_column": filter_column,
            "filter_value": filter_value,
        },
        "error": "",
    }


def _summary(path):
    rows, columns = _read_csv(path)
    stats = _build_stats(rows, columns)
    text = (
        f"CSV analyse: {path}\n"
        f"Lignes: {stats['rows']}\n"
        f"Colonnes: {stats['columns_count']}\n"
        f"Noms colonnes: {', '.join(stats['columns'])}\n"
        f"Valeurs nulles: {stats['null_values']}\n"
        f"Types detectes: {stats['types']}"
    )

    return {
        "success": True,
        "data": text,
        "count": len(rows),
        "stats": stats,
        "error": "",
    }


def _read_csv(path):
    if not path:
        raise ValueError("path est requis")

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"CSV introuvable: {file_path}")

    try:
        return _read_csv_with_encoding(file_path, "utf-8")
    except UnicodeDecodeError:
        return _read_csv_with_encoding(file_path, "latin-1")


def _read_csv_with_encoding(path, encoding):
    with Path(path).open("r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file)
        rows = [dict(row) for row in reader]
        columns = reader.fieldnames or []
        return rows, columns


def _build_stats(rows, columns):
    null_values = {}
    detected_types = {}

    for column in columns:
        values = [row.get(column, "") for row in rows]
        null_values[column] = sum(1 for value in values if value in ("", None))
        detected_types[column] = _detect_type(values)

    return {
        "rows": len(rows),
        "columns_count": len(columns),
        "columns": columns,
        "null_values": null_values,
        "types": detected_types,
        "sample": rows[:5],
    }


def _detect_type(values):
    non_empty = [value for value in values if value not in ("", None)]

    if not non_empty:
        return "empty"

    if all(_is_int(value) for value in non_empty):
        return "int"

    if all(_is_float(value) for value in non_empty):
        return "float"

    return "string"


def _matches(current, expected, operator):
    current_text = str(current)
    expected_text = str(expected)

    if operator == "equals":
        return current_text == expected_text

    if operator == "contains":
        return expected_text.lower() in current_text.lower()

    if operator == "gt":
        return _to_float(current_text) > _to_float(expected_text)

    if operator == "lt":
        return _to_float(current_text) < _to_float(expected_text)

    return False


def _sort_value(value):
    text = str(value)

    if _is_float(text):
        return _to_float(text)

    return text.lower()


def _is_int(value):
    try:
        int(str(value))
        return True
    except ValueError:
        return False


def _is_float(value):
    try:
        float(str(value))
        return True
    except ValueError:
        return False


def _to_float(value):
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _error(message):
    return {
        "success": False,
        "data": None,
        "count": 0,
        "stats": {},
        "error": message,
    }
