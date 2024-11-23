from cognite.neat import NeatSession
from pathlib import Path
from rich import print
THIS_FOLDER = Path(__file__).resolve().parent

XLSX_FILE = THIS_FOLDER / "classic_to_core_mapping.xlsx"

TARGET_FILE = THIS_FOLDER.parent / "cognite" / "neat" / "_rules" / "models" / "mapping" / "_classic2core.yaml"

def main() -> None:
    neat = NeatSession()

    neat.read.excel(XLSX_FILE)
    print(f"[bold green]Read {XLSX_FILE.name}[/bold green]")
    neat.verify()
    print("[bold green]Verified[/bold green]")

    neat.to.yaml(TARGET_FILE, format="neat")
    print(f"[bold green]Wrote {TARGET_FILE.name}[/bold green]")

if __name__ == "__main__":
    main()
