from pathlib import Path

import pandas as pd

from cognite.neat._session import _state_machine as states
from cognite.neat._session._session import NeatSession
from tests.config import DATA_FOLDER


def markdown_to_dict(file_path: Path) -> dict:
    # Parse the markdown table into a pandas DataFrame
    df = pd.read_csv(file_path, sep="|", skipinitialspace=True)

    # Clean up the DataFrame by removing empty columns and whitespace
    df = df.dropna(axis=1, how="all")  # Remove empty columns
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)  # Strip whitespace

    df = df[~df.astype(str).apply(lambda x: x.str.contains("---")).any(axis=1)]

    df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()
    state_transition_state = {
        row["state"]: {col: row[col] for col in df.columns if col != "state"} for _, row in df.iterrows()
    }

    # Remove the "Forbidden" state as it anyhow covered in table, and we need to test only revert mechaism
    state_transition_state.pop("Forbidden", None)

    return state_transition_state


def mermaid_to_dict(file_path: Path) -> dict:
    lines = file_path.read_text().strip().split("\n")

    state_transition_state: dict[str, dict[str, str]] = {}

    for line in lines:
        line = line.strip()

        # Skip header and empty lines
        if not line or line == "stateDiagram-v2":
            continue

        # Parse transitions (format: "stateA --> stateB : eventName")
        if "-->" in line:
            parts = line.split(" --> ")
            if len(parts) == 2:
                from_state = parts[0].strip()
                rest = parts[1].split(" : ")
                to_state = rest[0].strip()
                event = rest[1].strip().replace(" ", "_").lower() if len(rest) > 1 else ""

                if from_state not in state_transition_state:
                    state_transition_state[from_state] = {}
                state_transition_state[from_state][event] = to_state

    return state_transition_state


def test_defined_state_transitions_from_markdown() -> None:
    state_transition_state = markdown_to_dict(DATA_FOLDER / "_misc" / "state_machine_table.md")

    for state, transitions in state_transition_state.items():
        state_cls = getattr(states, f"{state}State")

        current_state = state_cls()

        for event, to_state in transitions.items():
            new_state = current_state.on_event(event)
            assert isinstance(new_state, getattr(states, f"{to_state}State"))

            # specially testing return mechanism
            if isinstance(new_state, states.ForbiddenState):
                assert new_state.previous_state == current_state

                # Testing that any event from ForbiddenState returns to previous state
                assert new_state.on_event("undo") == current_state


def test_defined_state_transitions_from_mermaid() -> None:
    state_transition_state = mermaid_to_dict(DATA_FOLDER / "_misc" / "state_machine_diagram.md")

    for state, transitions in state_transition_state.items():
        state_cls = getattr(states, f"{state}State")

        current_state = state_cls()

        for event, to_state in transitions.items():
            new_state = current_state.on_event(event)
            assert isinstance(new_state, getattr(states, f"{to_state}State"))

            # specially testing return mechanism
            if isinstance(new_state, states.ForbiddenState):
                assert new_state.previous_state == current_state


def test_one_end_to_end_workflow() -> None:
    session = NeatSession()

    assert isinstance(session.state, states.EmptyState)

    workflow_steps = [
        ("read_instances", states.InstancesState, "📊 Load instance data"),
        ("transform_instances", states.InstancesState, "🔄 transform instances"),
        ("infer_conceptual", states.InstancesConceptualState, "🧠 Infer conceptual model from instances"),
        ("transform_conceptual", states.InstancesConceptualState, "✏️  Refine conceptual model"),
        ("convert_to_physical", states.InstancesConceptualPhysicalState, "🏗️  Convert to physical model"),
        ("write_physical", states.InstancesConceptualPhysicalState, "💾 Export physical model"),
        ("write_conceptual", states.InstancesConceptualPhysicalState, "💾 Export conceptual model"),
        ("write_instances", states.InstancesConceptualPhysicalState, "💾 Export instances"),
        # Now try some forbidden operations
        ("read_instances", states.InstancesConceptualPhysicalState, "❌ Try to read more instances"),
        ("infer_conceptual", states.InstancesConceptualPhysicalState, "❌ Try to infer again"),
    ]

    for event, state, description in workflow_steps:
        success = session._execute_event(event)

        if "❌" in description:
            assert not success, f"Event '{event}' should be forbidden."

            # this is previous state to which session returns from ForbiddenState
            assert isinstance(session.state, states.InstancesConceptualPhysicalState)
        else:
            assert success, f"Event '{event}' should be allowed."
            assert isinstance(session.state, state)
