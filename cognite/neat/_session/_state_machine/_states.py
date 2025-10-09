from ._base import State


class EmptyState(State):
    """
    The initial state with empty NEAT store.
    """

    def on_event(self, event: str) -> State:
        if event == "read_instances":
            return InstancesState()
        elif event == "read_conceptual":
            return ConceptualState()
        elif event == "read_physical":
            return PhysicalState()

        return ForbiddenState(self)


class InstancesState(State):
    """
    State with instances loaded to the store.
    """

    def on_event(self, event: str) -> State:
        # One can keep on reading instances to stay in the same state
        if event == "read_instances":
            return InstancesState()
        # We either read conceptual model or infer it from instances
        # if read conceptual, we need to make sure that conceptual model is compatible with instances
        elif event in ["infer_conceptual", "read_conceptual"]:
            return InstancesConceptualState()

        # transforming instances keeps us in the same state
        elif event == "transform_instances":
            return InstancesState()
        # we should allow writing out instances in RDF format but not to CDF
        elif event == "write_instances":
            return InstancesState()

        # all other operations are forbidden
        return ForbiddenState(self)


class ConceptualState(State):
    """
    State with conceptual model loaded.
    """

    def on_event(self, event: str) -> State:
        # re-reading of model means transformation of
        # the current model has been done outside of NeatSession
        # requires checking that the new model is compatible with the existing
        if event == "read_conceptual":
            return ConceptualState()

        # when reading: requires linking between models
        # when converting: links are automatically created
        elif event == "read_physical" or event == "convert_to_physical":
            return ConceptualPhysicalState()
        elif event == "transform_conceptual":
            return ConceptualState()
        elif event == "write_conceptual":
            return ConceptualState()

        return ForbiddenState(self)


class PhysicalState(State):
    """
    State with physical model loaded.
    """

    def on_event(self, event: str) -> State:
        if event == "read_physical":
            return PhysicalState()
        elif event == "transform_physical":
            return PhysicalState()
        elif event == "write_physical":
            return PhysicalState()
        elif event == "convert_to_conceptual" or event == "read_conceptual":
            return ConceptualPhysicalState()

        return ForbiddenState(self)


class InstancesConceptualState(State):
    """
    State with both instances and conceptual model loaded.
    """

    def on_event(self, event: str) -> State:
        if event == "read_conceptual":
            return InstancesConceptualState()
        elif event == "transform_conceptual":
            return InstancesConceptualState()
        elif event in ["write_instances", "write_conceptual"]:
            return InstancesConceptualState()
        elif event in ["read_physical", "convert_to_physical"]:
            return InstancesConceptualPhysicalState()

        return ForbiddenState(self)


class ConceptualPhysicalState(State):
    """
    State with both conceptual and physical models loaded.
    """

    def on_event(self, event: str) -> State:
        if event == "read_physical":
            return ConceptualPhysicalState()
        elif event == "transform_physical":
            return ConceptualPhysicalState()
        elif event in ["write_conceptual", "write_physical"]:
            return ConceptualPhysicalState()

        return ForbiddenState(self)


class InstancesConceptualPhysicalState(State):
    """
    State with instances, conceptual, and physical models loaded.
    """

    def on_event(self, event: str) -> State:
        if event == "read_physical":
            return InstancesConceptualPhysicalState()
        elif event == "transform_physical":
            return InstancesConceptualPhysicalState()
        elif event in ["write_instances", "write_conceptual", "write_physical"]:
            return InstancesConceptualPhysicalState()

        return ForbiddenState(self)


class ForbiddenState(State):
    """
    State representing forbidden transitions - returns to previous state.
    """

    def __init__(self, previous_state: State):
        self.previous_state = previous_state
        print(f"Forbidden action attempted. Returning to previous state: {previous_state}")

    def on_event(self, event: str) -> State:
        # only "undo" to trigger going back to previous state
        if event.strip().lower() == "undo":
            return self.previous_state
        return self
