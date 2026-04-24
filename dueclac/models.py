from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


def money_zero() -> Decimal:
    return Decimal("0")


@dataclass
class TraderRecord:
    trader_name: str
    group: str
    opening: Decimal = field(default_factory=money_zero)
    sales: Decimal = field(default_factory=money_zero)
    sales_return: Decimal = field(default_factory=money_zero)
    net_sales: Decimal = field(default_factory=money_zero)
    purchase: Decimal = field(default_factory=money_zero)
    pur_return: Decimal = field(default_factory=money_zero)
    receive: Decimal = field(default_factory=money_zero)
    payment: Decimal = field(default_factory=money_zero)
    other_cr: Decimal = field(default_factory=money_zero)
    other_dr: Decimal = field(default_factory=money_zero)
    receipt_cheque: Decimal = field(default_factory=money_zero)
    paid_cheque: Decimal = field(default_factory=money_zero)
    discount: Decimal = field(default_factory=money_zero)
    rebate: Decimal = field(default_factory=money_zero)
    due: Decimal = field(default_factory=money_zero)
    new_due: Decimal = field(default_factory=money_zero)

    def calculate_new_due(self) -> Decimal:
        self.new_due = self.net_sales - (
            self.receive + self.purchase + self.payment + self.discount
        )
        return self.new_due

    def should_include_in_due_report(self) -> bool:
        if self.net_sales <= 0:
            return False
        if self.due <= 0:
            return False
        if self.opening == self.due:
            return False
        if self.net_sales <= (self.receive + self.purchase):
            return False
        return True

    def to_output_row(self) -> dict[str, float | str]:
        return {
            "Trader Name": self.trader_name,
            "Group": self.group,
            "Net Sales": float(self.net_sales),
            "Receive": float(self.receive),
            "New Due": float(self.new_due),
            "Total Due": float(self.due),
        }


@dataclass
class ReportData:
    title: str
    date_range: str
    records: list[TraderRecord]
    extracted_rows: int = 0
    exported_rows: int = 0

    @property
    def total_new_due(self) -> Decimal:
        return sum((record.new_due for record in self.records), start=Decimal("0"))

    @property
    def total_due(self) -> Decimal:
        return sum((record.due for record in self.records), start=Decimal("0"))

