from pathlib import Path

import pandas as pd

from cognite.neat import _state_machine as states
from cognite.neat._session._session import NeatSession
from tests.config import DATA_FOLDER


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
