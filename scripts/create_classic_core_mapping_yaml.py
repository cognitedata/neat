from cognite.neat import NeatSession, get_cognite_client
from pathlib import Path
from rich import print
THIS_FOLDER = Path(__file__).resolve().parent

XLSX_FILE = THIS_FOLDER / "core_classic_mapping.xlsx"

TARGET_FILE = THIS_FOLDER.parent / "cognite" / "neat" / "_rules" / "models" / "mapping" / "_classic2core.yaml"

def main() -> None:
    client = get_cognite_client(".env")
    neat = NeatSession(client)

    issues = neat.read.excel(XLSX_FILE)
    if issues.has_errors:
        neat.inspect.issues()
        return
    print(f"[bold green]Read {XLSX_FILE.name}[/bold green]")
    issues = neat.verify()
    if issues.has_errors:
        neat.inspect.issues()
        return
    print("[bold green]Verified[/bold green]")

    neat.to.yaml(TARGET_FILE, format="neat")
    print(f"[bold green]Wrote {TARGET_FILE.name}[/bold green]")

if __name__ == "__main__":
    main()
