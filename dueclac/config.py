from __future__ import annotations

from typing import Iterable

SOURCE_COLUMNS = [
    "Opening",
    "Sales",
    "Sales Return",
    "Net Sales",
    "Purchase",
    "Pur.Return",
    "Receive",
    "Payment",
    "Other Cr",
    "Other Dr",
    "Recipt Chequ",
    "Paid Cheque",
    "Discount",
    "Rebate",
    "Due",
]

OUTPUT_COLUMNS = [
    "SL",
    "Trader Name",
    "Group",
    "Net Sales",
    "Receive",
    "New Due",
    "Total Due",
]

DEFAULT_GROUPS = [
    "Branch",
    "Cantonment",
    "Credit Customer",
    "Customer",
    "Customer Lock",
    "Employe",
    "Employee",
    "Hasan Bhai",
    "Modesty",
    "Lottary",
    "PZ Branch",
    "Resaler",
    "Resaler Biani Bazar",
    "Resaler Gallaria",
    "Resaler Kazi Mension",
    "Resaler Moulovi Bazar",
    "Resaler Planate Araf",
    "Resaler Sunam Gong",
    "Signal",
    "Supplier 1",
]

GROUP_KEYWORDS = {
    "branch",
    "cantonment",
    "credit",
    "customer",
    "lock",
    "employe",
    "employee",
    "hasan",
    "modesty",
    "lottery",
    "lottary",
    "pz",
    "resaler",
    "reseller",
    "supplier",
    "signal",
}


def build_group_list(extra_groups: Iterable[str] | None = None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for group_name in DEFAULT_GROUPS:
        normalized = normalize_key(group_name)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(group_name.strip())

    for group_name in extra_groups or []:
        cleaned = group_name.strip()
        normalized = normalize_key(cleaned)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(cleaned)

    return ordered


def normalize_key(value: str) -> str:
    return " ".join(value.upper().split())
