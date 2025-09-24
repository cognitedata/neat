from pathlib import Path
from rich import print

from cognite.neat.v0.core._data_model.exporters import YAMLExporter
from cognite.neat.v0.core._data_model.importers import ExcelImporter
from cognite.neat.v0.core._data_model.transformers import VerifyPhysicalDataModel

THIS_FOLDER = Path(__file__).resolve().parent
XLSX_FILE = THIS_FOLDER / "core_classic_mapping.xlsx"
TARGET_FILE = THIS_FOLDER.parent / "cognite" / "neat" / "_rules" / "models" / "mapping" / "_classic2core.yaml"


def main() -> None:
    read_rules = ExcelImporter(XLSX_FILE).to_data_model()
    print(f"[bold green]Read {XLSX_FILE.name}[/bold green]")

    dms_rules = VerifyPhysicalDataModel(validate=False).transform(read_rules)
    print("[bold green]Verified[/bold green]")

    YAMLExporter().export_to_file(dms_rules, TARGET_FILE)
    print(f"[bold green]Wrote {TARGET_FILE.name}[/bold green]")


if __name__ == "__main__":
    main()
