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

    def location(self, path: tuple[int | str, ...]) -> str:
        table_id: str | None = None
        row_no: int | None = None
        column: str | None = None
        if len(path) >= 1 and isinstance(path[0], str):
            table_id = path[0]
        if len(path) >= 2 and isinstance(path[1], int):
            row_no = path[1]
        if len(path) >= 3 and isinstance(path[2], str):
            column = path[2]
        table_read = table_id and self.table_read.get(table_id)
        if table_read and isinstance(row_no, int):
            row_no = table_read.adjusted_row_number(row_no)
        elif isinstance(row_no, int):
            row_no = row_no + 1  # Convert to 1-indexed if no table read info is available
        location_parts = []
        if table_id is not None:
            location_parts.append(f"table '{table_id}'")
        if row_no is not None:
            location_parts.append(f"row {row_no}")
        if column is not None:
            location_parts.append(f"column {column}")
        if len(path) > 4:
            location_parts.append("-> " + ".".join(str(p) for p in path[3:]))

        return " ".join(location_parts)
