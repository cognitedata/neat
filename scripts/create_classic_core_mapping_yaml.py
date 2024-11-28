from datetime import datetime, timezone

from cognite.neat import NeatSession, get_cognite_client
from pathlib import Path
from rich import print

from cognite.neat._rules.transformers import VerifyDMSRules
from cognite.neat._store._provenance import Change

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
    # Redoing the .verify to skip the validation step.
    start = datetime.now(timezone.utc)
    transformer = VerifyDMSRules("continue", validate=False)
    source_id, last_unverified_rule = neat._state.data_model.last_unverified_rule
    result = transformer.transform(last_unverified_rule)
    end = datetime.now(timezone.utc)
    issues = result.issues
    if issues.has_errors:
        neat.inspect.issues()
        return

    print("[bold green]Verified[/bold green]")
    change = Change.from_rules_activity(
        result.rules,
        transformer.agent,
        start,
        end,
        f"Verified data model {source_id} as {result.rules.metadata.identifier}",
        neat._state.data_model.provenance.source_entity(source_id)
        or neat._state.data_model.provenance.target_entity(source_id),
    )

    neat._state.data_model.write(result.rules, change)

    neat.to.yaml(TARGET_FILE, format="neat")
    print(f"[bold green]Wrote {TARGET_FILE.name}[/bold green]")

if __name__ == "__main__":
    main()
