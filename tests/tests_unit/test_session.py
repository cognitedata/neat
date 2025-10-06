from cognite.neat._session._session import NeatSession
from cognite.neat._session._state_machine import EmptyState


def test_init_with_client() -> None:
    session = NeatSession()

    assert isinstance(session.state, EmptyState)

    workflow_steps = [
        ("read_instances", "📊 Load instance data"),
        ("transform_instances", "🔄 transform instances"),
        ("infer_conceptual", "🧠 Infer conceptual model from instances"),
        ("transform_conceptual", "✏️  Refine conceptual model"),
        ("convert_physical", "🏗️  Convert to physical model"),
        ("write_physical", "💾 Export physical model"),
        ("write_conceptual", "💾 Export conceptual model"),
        ("write_instances", "💾 Export instances"),
        # Now try some forbidden operations
        ("read_instances", "❌ Try to read more instances"),
        ("infer_conceptual", "❌ Try to infer again"),
    ]

    for event, description in workflow_steps:
        success = session._execute_event(event)
        if "❌" in description:
            assert not success, f"Event '{event}' should be forbidden."
        else:
            assert success, f"Event '{event}' should be allowed."
