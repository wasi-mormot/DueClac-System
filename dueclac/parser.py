from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

import pdfplumber

from .config import GROUP_KEYWORDS, SOURCE_COLUMNS, build_group_list, normalize_key
from .models import ReportData, TraderRecord

DATE_RANGE_RE = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{4}\s+To\s+\d{1,2}/\d{1,2}/\d{4}\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![\w/])\(?-?\d[\d,]*\.?\d*\)?(?![\w/])")
PARENTHETICAL_RE = re.compile(r"^\([^)]*\)$")

IGNORABLE_PREFIX_WORDS = {
    "area",
    "office",
    "gallary",
    "gallery",
    "pur",
    "electronics",
    "electronic",
    "computer",
    "technology",
    "technologies",
    "world",
    "customer",
    "branch",
    "airport",
    "madrasa",
    "bazar",
    "sylhet",
    "new",
    "garage",
    "garrage",
}

NAME_SUFFIX_WORDS = {
    "association",
    "brothers",
    "center",
    "centre",
    "communication",
    "computer",
    "computers",
    "corporation",
    "design",
    "electronics",
    "electronic",
    "enterprise",
    "house",
    "limited",
    "ltd",
    "solution",
    "solutions",
    "spices",
    "studio",
    "technology",
    "technologies",
    "world",
}


@dataclass
class ParsedRow:
    trader_name_fragment: str
    values: list[Decimal]


class DueClacPDFParser:
    def __init__(self, known_groups: Iterable[str] | None = None) -> None:
        group_list = build_group_list(known_groups)
        self.known_groups_map = {normalize_key(name): name.strip() for name in group_list}

    def parse(self, pdf_path: str | Path) -> ReportData:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        title_candidates: list[str] = []
        skipped_header_lines: set[str] = set()
        report_lines: list[str] = []
        date_range = ""
        started = False

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                for raw_line in text.splitlines():
                    line = self._clean_line(raw_line)
                    if not line or self._is_footer_line(line):
                        continue

                    if not started:
                        date_match = DATE_RANGE_RE.search(line)
                        if date_match:
                            date_range = self._normalize_date_range(date_match.group(0))
                            started = True
                            skipped_header_lines.update(
                                normalize_key(candidate) for candidate in title_candidates
                            )
                            continue

                        if self._is_meaningful_pre_report_line(line):
                            title_candidates.append(line)
                        continue

                    if self._should_skip_post_start_line(line, date_range, skipped_header_lines):
                        continue

                    report_lines.append(line)

        if not started or not date_range:
            raise ValueError(
                "Could not find the date range in the PDF. Make sure the report is text-copyable."
            )

        title = self._select_title(title_candidates) or "DueClac Financial Report"
        filtered_records, extracted_rows = self._parse_records(report_lines)
        return ReportData(
            title=title,
            date_range=date_range,
            records=filtered_records,
            extracted_rows=extracted_rows,
            exported_rows=len(filtered_records),
        )

    def _parse_records(self, lines: list[str]) -> tuple[list[TraderRecord], int]:
        records: list[TraderRecord] = []
        current_group = ""
        pending_name_lines: list[str] = []
        extracted_rows = 0
        last_record: TraderRecord | None = None

        for index, line in enumerate(lines):
            next_line = self._next_relevant_line(lines, index + 1)
            next_next_line = self._next_relevant_line(lines, index + 2)

            if self._is_subtotal_line(line):
                pending_name_lines.clear()
                last_record = None
                continue

            if self._is_header_line(line):
                continue

            if self._looks_like_group_header(line, next_line=next_line, next_next_line=next_next_line):
                current_group = self._clean_group_name(line)
                pending_name_lines.clear()
                last_record = None
                continue

            parsed_row = self._try_parse_row(line)
            if parsed_row:
                extracted_rows += 1
                name_parts: list[str] = []
                if self._should_prepend_pending_lines(
                    pending_name_lines=pending_name_lines,
                    current_name=parsed_row.trader_name_fragment,
                ):
                    name_parts.extend(pending_name_lines)
                if parsed_row.trader_name_fragment:
                    name_parts.append(parsed_row.trader_name_fragment)

                trader_name = self._combine_name_parts(name_parts)
                if not trader_name:
                    trader_name = "Unknown Trader"

                record = self._build_record(
                    trader_name=trader_name,
                    group_name=current_group or "Ungrouped",
                    values=parsed_row.values,
                )
                pending_name_lines.clear()
                last_record = record

                if record.should_include_in_due_report():
                    record.calculate_new_due()
                    records.append(record)
                continue

            if self._should_attach_to_previous_record(line=line, last_record=last_record):
                last_record.trader_name = self._combine_name_parts([last_record.trader_name, line])
                continue

            pending_name_lines.append(line)

        return records, extracted_rows

    def _build_record(
        self,
        trader_name: str,
        group_name: str,
        values: list[Decimal],
    ) -> TraderRecord:
        padded_values = list(values)
        if len(padded_values) < len(SOURCE_COLUMNS):
            padded_values = [Decimal("0")] * (len(SOURCE_COLUMNS) - len(padded_values)) + padded_values
        elif len(padded_values) > len(SOURCE_COLUMNS):
            padded_values = padded_values[-len(SOURCE_COLUMNS) :]

        return TraderRecord(
            trader_name=trader_name,
            group=group_name,
            opening=padded_values[0],
            sales=padded_values[1],
            sales_return=padded_values[2],
            net_sales=padded_values[3],
            purchase=padded_values[4],
            pur_return=padded_values[5],
            receive=padded_values[6],
            payment=padded_values[7],
            other_cr=padded_values[8],
            other_dr=padded_values[9],
            receipt_cheque=padded_values[10],
            paid_cheque=padded_values[11],
            discount=padded_values[12],
            rebate=padded_values[13],
            due=padded_values[14],
        )

    def _try_parse_row(self, line: str) -> ParsedRow | None:
        matches = list(NUMBER_RE.finditer(line))
        if len(matches) < 5:
            return None

        selected_matches = matches[-len(SOURCE_COLUMNS) :]
        first_value_start = selected_matches[0].start()
        trader_name_fragment = self._clean_name_fragment(line[:first_value_start])
        values = [self._to_decimal(match.group(0)) for match in selected_matches]
        return ParsedRow(trader_name_fragment=trader_name_fragment, values=values)

    def _should_skip_post_start_line(
        self,
        line: str,
        date_range: str,
        skipped_header_lines: set[str],
    ) -> bool:
        normalized = normalize_key(line)

        if normalized == normalize_key(date_range):
            return True
        if normalized in skipped_header_lines:
            return True
        if self._is_footer_line(line):
            return True
        if self._is_subtotal_line(line):
            return True
        return False

    def _should_prepend_pending_lines(self, pending_name_lines: list[str], current_name: str) -> bool:
        cleaned_pending = [self._clean_name_fragment(line) for line in pending_name_lines if line.strip()]
        cleaned_pending = [line for line in cleaned_pending if line]
        if not cleaned_pending:
            return False

        if any(self._ends_with_continuation_marker(line) for line in cleaned_pending):
            return True

        if len(cleaned_pending) == 1:
            line = cleaned_pending[0]
            if self._is_parenthetical_tag(line):
                return False
            if self._looks_like_ignorable_prefix(line):
                return False
            return self._looks_like_generic_name_fragment(current_name)

        if all(self._looks_like_ignorable_prefix(line) for line in cleaned_pending):
            return False

        return self._looks_like_generic_name_fragment(current_name)

    def _should_attach_to_previous_record(
        self,
        line: str,
        last_record: TraderRecord | None,
    ) -> bool:
        if last_record is None:
            return False
        if not line or self._try_parse_row(line) is not None:
            return False
        if self._is_header_line(line) or self._is_subtotal_line(line) or self._is_footer_line(line):
            return False

        previous_name = self._clean_name_fragment(last_record.trader_name)
        if not previous_name:
            return False

        if self._ends_with_continuation_marker(previous_name):
            return True

        if self._is_parenthetical_tag(line):
            return previous_name.endswith("(")

        words = line.replace("(", "").replace(")", "").split()
        normalized_words = [word.strip(".,").lower() for word in words if word.strip(".,")]
        if not normalized_words:
            return False

        return len(words) <= 2 and all(word in NAME_SUFFIX_WORDS for word in normalized_words)

    def _looks_like_group_header(
        self,
        line: str,
        next_line: str | None,
        next_next_line: str | None,
    ) -> bool:
        normalized = normalize_key(line)
        if not normalized:
            return False

        if normalized in self.known_groups_map:
            return True

        if self._try_parse_row(line) is not None:
            return False
        if self._is_header_line(line) or self._is_subtotal_line(line) or self._is_footer_line(line):
            return False

        next_is_header = self._is_header_line(next_line or "")
        next_next_is_header = self._is_header_line(next_next_line or "")
        if next_is_header or next_next_is_header:
            return True

        words = line.split()
        lower_line = line.lower()
        has_keyword = any(keyword in lower_line for keyword in GROUP_KEYWORDS)
        short_enough = len(words) <= 5 and len(line) <= 40
        return short_enough and has_keyword

    def _select_title(self, title_candidates: list[str]) -> str:
        if not title_candidates:
            return ""

        for candidate in title_candidates:
            lower = candidate.lower()
            if "platonic" in lower or "zone" in lower:
                return candidate

        for candidate in title_candidates:
            if not any(character.isdigit() for character in candidate):
                return candidate

        return title_candidates[0]

    def _is_meaningful_pre_report_line(self, line: str) -> bool:
        if self._is_contact_line(line) or self._is_footer_line(line):
            return False
        return bool(re.search(r"[A-Za-z]", line))

    def _is_contact_line(self, line: str) -> bool:
        lower = line.lower()
        contact_keywords = [
            "email",
            "mobile",
            "phone",
            "fax",
            "road",
            "house",
            "block",
            "plot",
            "address",
            "website",
            "@",
            "www.",
        ]
        return any(keyword in lower for keyword in contact_keywords)

    def _is_footer_line(self, line: str) -> bool:
        lower = line.lower()
        if "print date" in lower or "print time" in lower or "printed on" in lower:
            return True
        if re.fullmatch(r"page\s*\d+(\s*of\s*\d+)?", lower):
            return True
        if re.fullmatch(r"\d+\s*of\s*\d+", lower):
            return True
        if re.fullmatch(r"\d+", line.strip()):
            return True
        if lower.startswith("page "):
            return True
        return False

    def _is_subtotal_line(self, line: str) -> bool:
        normalized = normalize_key(line)
        return normalized.startswith("SUBTOTAL") or normalized.startswith("SUB TOTAL")

    def _is_header_line(self, line: str) -> bool:
        lower = line.lower()
        header_keywords = [
            "tradername",
            "trader name",
            "opening",
            "sales",
            "sales return",
            "net sales",
            "purchase",
            "pur.return",
            "receive",
            "payment",
            "other cr",
            "other dr",
            "recipt chequ",
            "receipt chequ",
            "paid cheque",
            "discount",
            "rebate",
            "due",
        ]

        if "tradername" in lower or "trader name" in lower:
            return True

        keyword_hits = sum(1 for keyword in header_keywords if keyword in lower)
        return keyword_hits >= 4

    def _clean_group_name(self, group_name: str) -> str:
        normalized = normalize_key(group_name)
        return self.known_groups_map.get(normalized, group_name.strip())

    def _is_parenthetical_tag(self, value: str) -> bool:
        return bool(PARENTHETICAL_RE.fullmatch(value.strip()))

    def _looks_like_ignorable_prefix(self, value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return True
        if self._is_parenthetical_tag(stripped):
            return True

        words = stripped.replace("(", "").replace(")", "").split()
        normalized_words = [word.strip(".,").lower() for word in words if word.strip(".,")]
        if not normalized_words:
            return True
        if len(normalized_words) == 1:
            return True
        return all(word in IGNORABLE_PREFIX_WORDS for word in normalized_words)

    def _looks_like_generic_name_fragment(self, value: str) -> bool:
        words = value.replace("(", "").replace(")", "").split()
        normalized_words = [word.strip(".,").lower() for word in words if word.strip(".,")]
        if not normalized_words:
            return False
        if len(normalized_words) == 1:
            return normalized_words[0] in NAME_SUFFIX_WORDS
        return all(word in NAME_SUFFIX_WORDS for word in normalized_words)

    def _ends_with_continuation_marker(self, value: str) -> bool:
        stripped = value.rstrip()
        if not stripped:
            return False
        return stripped.endswith(("&", "(", "/", "-"))

    def _combine_name_parts(self, parts: Iterable[str]) -> str:
        cleaned_parts: list[str] = []
        for part in parts:
            cleaned = self._clean_name_fragment(part)
            if not cleaned:
                continue
            if cleaned_parts and normalize_key(cleaned_parts[-1]) == normalize_key(cleaned):
                continue
            cleaned_parts.append(cleaned)
        return " ".join(cleaned_parts).strip()

    def _clean_name_fragment(self, value: str) -> str:
        cleaned = self._clean_line(value)
        cleaned = cleaned.strip("-,:")
        return cleaned

    def _clean_line(self, raw_line: str) -> str:
        line = raw_line.replace("\xa0", " ")
        line = re.sub(r"\s+", " ", line)
        return line.strip()

    def _normalize_date_range(self, value: str) -> str:
        return re.sub(r"\s+to\s+", " To ", value, flags=re.IGNORECASE).strip()

    def _next_relevant_line(self, lines: list[str], start_index: int) -> str | None:
        for line in lines[start_index:]:
            if line and not self._is_footer_line(line):
                return line
        return None

    def _to_decimal(self, value: str) -> Decimal:
        cleaned = value.replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = f"-{cleaned[1:-1]}"
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal("0")
