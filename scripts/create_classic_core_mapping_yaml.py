from pathlib import Path
from rich import print

from cognite.neat._rules.exporters import YAMLExporter
from cognite.neat._rules.importers import ExcelImporter
from cognite.neat._rules.transformers import VerifyDMSRules

THIS_FOLDER = Path(__file__).resolve().parent
XLSX_FILE = THIS_FOLDER / "core_classic_mapping.xlsx"
TARGET_FILE = THIS_FOLDER.parent / "cognite" / "neat" / "_rules" / "models" / "mapping" / "_classic2core.yaml"


def main() -> None:
    read_rules = ExcelImporter(XLSX_FILE).to_rules()
    print(f"[bold green]Read {XLSX_FILE.name}[/bold green]")

    dms_rules = VerifyDMSRules(validate=False).transform(read_rules)
    print("[bold green]Verified[/bold green]")

    YAMLExporter().export_to_file(dms_rules, TARGET_FILE)
    print(f"[bold green]Wrote {TARGET_FILE.name}[/bold green]")


if __name__ == "__main__":
    main()
