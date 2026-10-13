from __future__ import annotations

import re
import csv
import zipfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".sha256", ".svg"}
DOCX_TEXT_PREFIXES = ("word/", "docProps/")
MAX_DOCX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_DOCX_TOTAL_XML_BYTES = 32 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
FORBIDDEN_FIELD_NAMES = {
    "user_id",
    "raw_user_id",
    "subject_id",
    "name",
    "phone",
    "email",
    "resident_registration_number",
    "db_host",
    "db_password",
    "access_token",
    "authorization",
    "connection_string",
}
SENSITIVE_PATTERNS = {
    "CONNECTION_STRING": re.compile(r"\b(?:postgres|postgresql)://[^\s\"']+", re.I),
    "SECRET_ASSIGNMENT": re.compile(
        r"[\"']?\b(?:DB_HOST|DB_NAME|DB_USERNAME|DB_USER|DB_PASSWORD|PASSWORD|ACCESS_TOKEN|API_KEY|SECRET|CONNECTION_STRING)\b[\"']?\s*[:=]\s*[\"']?[^\s,}\"']+",
        re.I,
    ),
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "AWS_ACCESS_KEY": re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    "JWT": re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    "BEARER_TOKEN": re.compile(r"\bAuthorization\s*:\s*Bearer\s+\S+", re.I),
    "RAW_IDENTIFIER_ASSIGNMENT": re.compile(
        r"[\"']?\b(?:user_id|raw_user_id|subject_id)\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._-]{3,}",
        re.I,
    ),
    "UUID_IDENTIFIER": re.compile(
        r"(?<![A-Za-z0-9])(?:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})(?![A-Za-z0-9])",
        re.I,
    ),
    "EMAIL_ADDRESS": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "KOREAN_MOBILE": re.compile(r"(?<![A-Za-z0-9])01[016789][- ]?\d{3,4}[- ]?\d{4}(?![A-Za-z0-9])"),
    "RESIDENT_REGISTRATION_NUMBER": re.compile(r"(?<![A-Za-z0-9])\d{6}[- ]?[1-8]\d{6}(?![A-Za-z0-9])"),
}


def scan_text(text: str) -> list[str]:
    return sorted(name for name, pattern in SENSITIVE_PATTERNS.items() if pattern.search(text))


def scan_output_tree(root: Path) -> dict[str, Any]:
    finding_keys: set[tuple[str, str]] = set()
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "security_scan.json":
            continue
        relative = str(path.relative_to(root))
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            scanned += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            for finding_type in scan_text(text):
                finding_keys.add((relative, finding_type))
            if suffix == ".csv":
                with path.open("r", encoding="utf-8", newline="") as stream:
                    header = next(csv.reader(stream), [])
                if {name.strip().lower() for name in header} & FORBIDDEN_FIELD_NAMES:
                    finding_keys.add((relative, "FORBIDDEN_OUTPUT_FIELD"))
        elif suffix == ".parquet":
            scanned += 1
            parquet = pq.ParquetFile(path)
            fields = parquet.schema_arrow
            if {field.name.lower() for field in fields} & FORBIDDEN_FIELD_NAMES:
                finding_keys.add((relative, "FORBIDDEN_OUTPUT_FIELD"))
            string_columns = [
                field.name
                for field in fields
                if pa.types.is_string(field.type) or pa.types.is_large_string(field.type)
            ]
            for row_group in range(parquet.num_row_groups):
                table = parquet.read_row_group(row_group, columns=string_columns)
                for column in string_columns:
                    for value in table[column].to_pylist():
                        if value is None:
                            continue
                        for finding_type in scan_text(str(value)):
                            finding_keys.add((relative, finding_type))
        elif suffix == ".docx":
            scanned += 1
            try:
                with zipfile.ZipFile(path) as archive:
                    total_xml_bytes = 0
                    for member in archive.infolist():
                        member_parts = Path(member.filename).parts
                        if member.filename.startswith(("/", "\\")) or ".." in member_parts:
                            finding_keys.add((relative, "UNSAFE_DOCX_MEMBER_PATH"))
                            continue
                        if (
                            not member.filename.startswith(DOCX_TEXT_PREFIXES)
                            or not member.filename.endswith((".xml", ".rels"))
                        ):
                            continue
                        total_xml_bytes += member.file_size
                        if total_xml_bytes > MAX_DOCX_TOTAL_XML_BYTES:
                            finding_keys.add((relative, "OVERSIZED_DOCX_XML"))
                            break
                        if member.file_size > MAX_DOCX_MEMBER_BYTES:
                            finding_keys.add((relative, "OVERSIZED_DOCX_XML"))
                            continue
                        if (
                            member.compress_size > 0
                            and member.file_size / member.compress_size
                            > MAX_DOCX_COMPRESSION_RATIO
                        ):
                            finding_keys.add((relative, "SUSPICIOUS_DOCX_COMPRESSION"))
                            continue
                        text = archive.read(member).decode("utf-8", errors="replace")
                        for finding_type in scan_text(text):
                            finding_keys.add((relative, finding_type))
            except (OSError, zipfile.BadZipFile, RuntimeError):
                finding_keys.add((relative, "UNREADABLE_DOCX"))
    findings = [
        {"file": file, "finding_type": finding_type}
        for file, finding_type in sorted(finding_keys)
    ]
    return {
        "status": "PASSED" if not findings else "FAILED_SECRET_OR_IDENTIFIER_SCAN",
        "scanned_text_file_count": scanned,
        "finding_count": len(findings),
        "findings": findings,
        "values_redacted": True,
    }


def assert_security_scan_passed(report: dict[str, Any]) -> None:
    if report.get("finding_count"):
        types = sorted({item["finding_type"] for item in report["findings"]})
        raise RuntimeError("SECURITY_SCAN_FAILED: " + ", ".join(types))
