from dataclasses import dataclass, field


@dataclass
class SpreadsheetRead:
    """This class is used to store information about the source spreadsheet.

    It is used to adjust row numbers to account for header rows and empty rows
    such that the error/warning messages are accurate.
    """

    header_row: int = 1
    empty_rows: list[int] = field(default_factory=list)
    skipped_rows: list[int] = field(default_factory=list)
    is_one_indexed: bool = True

    def __post_init__(self) -> None:
        self.empty_rows = sorted(self.empty_rows)

    def adjusted_row_number(self, row_no: int) -> int:
        output = row_no
        for empty_row in self.empty_rows:
            if empty_row <= output:
                output += 1
            else:
                break

        for skipped_rows in self.skipped_rows:
            if skipped_rows <= output:
                output += 1
            else:
                break

        return output + self.header_row + (1 if self.is_one_indexed else 0)


@dataclass
class TableSource:
    source: str
    table_read: dict[str, SpreadsheetRead] = field(default_factory=dict)

    def location(
        self,
        path: tuple[int | str, ...],
    ) -> str:
        if len(path) < 2:
            return f"in {self.source}"
        table_name = path[0]
        if table_name not in self.table_read:
            return f"in {self.source}, table {table_name!r}"
        table_info = self.table_read[table_name]
        if len(path) == 2:
            return f"in {self.source}, table {table_name!r}"
        row = path[1]
        if not isinstance(row, int):
            return f"in {self.source}, table {table_name!r}"
        adjusted_row = table_info.adjusted_row_number(row)
        if len(path) == 3:
            return f"in {self.source}, table {table_name!r}, row {adjusted_row}"
        column = path[2]
        return f"in {self.source}, table {table_name!r}, row {adjusted_row}, column {column!r}"
