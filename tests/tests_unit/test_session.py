from cognite.neat._session._session import NeatSession
from cognite.neat._session._state_machine import (
    EmptyState,
    InstancesConceptualPhysicalState,
    InstancesConceptualState,
    InstancesState,
)


def test_init_with_client() -> None:
    session = NeatSession()

    assert isinstance(session.state, EmptyState)

    workflow_steps = [
        ("read_instances", InstancesState, "📊 Load instance data"),
        ("transform_instances", InstancesState, "🔄 transform instances"),
        ("infer_conceptual", InstancesConceptualState, "🧠 Infer conceptual model from instances"),
        ("transform_conceptual", InstancesConceptualState, "✏️  Refine conceptual model"),
        ("convert_physical", InstancesConceptualPhysicalState, "🏗️  Convert to physical model"),
        ("write_physical", InstancesConceptualPhysicalState, "💾 Export physical model"),
        ("write_conceptual", InstancesConceptualPhysicalState, "💾 Export conceptual model"),
        ("write_instances", InstancesConceptualPhysicalState, "💾 Export instances"),
        # Now try some forbidden operations
        ("read_instances", InstancesConceptualPhysicalState, "❌ Try to read more instances"),
        ("infer_conceptual", InstancesConceptualPhysicalState, "❌ Try to infer again"),
    ]

    for event, state, description in workflow_steps:
        success = session._execute_event(event)
        if "❌" in description:
            assert not success, f"Event '{event}' should be forbidden."
        else:
            assert success, f"Event '{event}' should be allowed."
            assert isinstance(session.state, state)
