from pathlib import Path
from typing import Any, Literal

from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat._alpha import ExperimentalFlags
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.exporters import ExcelExporter
from cognite.neat._rules.importers import ExcelImporter
from cognite.neat._rules.models import InformationInputRules
from cognite.neat._rules.models.dms import DMSValidation
from cognite.neat._rules.transformers import (
    AddCogniteProperties,
    IncludeReferenced,
    ToDataProductModel,
    ToEnterpriseModel,
    ToSolutionModel,
    VerifiedRulesTransformer,
)
from cognite.neat._utils.reader import NeatReader, PathReader

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class TemplateAPI:
    """
    Create a template for a new data model.
    """

    def __init__(self, state: SessionState):
        self._state = state

    def enterprise_model(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "CopyOf",
        dummy_property: str = "GUID",
    ) -> IssueList:
        """Creates a template for an enterprise model based on the current data model in the session.
        An enterprise data model is a model that is used for read and write of instances. In addition,
        it is governed by the organization.
        The basis for an enterprise data model should be a Cognite Data Model.

        Args:
            data_model_id: The enterprise data model id that is being created
            org_name: Organization name to use for the views in the enterprise data model.
            dummy_property: The dummy property to use as placeholder for the views in the new data model.

        What does this function do?
            1. It creates a new view for each view in the current data model that implements the view it is based on.
            2. If dummy_property is set, it will create a container with one property for each view and connect the
               view to the container.
            3. It will repeat all connection properties in the new views and update the ValueTypes to match the new
               views.

        !!! note "Enterprise Data Model Creation"

            Always create an enterprise data model from a Cognite Data Model as this will
            assure all the Cognite Data Fusion applications to run smoothly, such as
                - Search
                - Atlas AI
                - Infield
                - Canvas
                - Maintain
                - Charts

        """
        last_rules = self._state.rule_store.last_verified_rules
        issues = self._state.rule_transform(
            ToEnterpriseModel(
                new_model_id=data_model_id,
                org_name=org_name,
                dummy_property=dummy_property,
                move_connections=True,
            )
        )
        if last_rules and not issues.has_errors:
            self._state.last_reference = last_rules
        return issues

    def solution_model(
        self,
        data_model_id: DataModelIdentifier,
        direct_property: str = "enterprise",
        view_prefix: str = "Enterprise",
    ) -> IssueList:
        """Creates a template for a solution model based on the current data model in the session.
        A solution data model is for read and write of instances.
        The basis for a solution data model should be an enterprise data model.

        Args:
            data_model_id: The solution data model id that is being created.
            direct_property: The property to use for the direct connection between the views in the solution data model
                and the enterprise data model.
            view_prefix: The prefix to use for the views in the enterprise data model.

        What does this function do?
        1. It will create two new views for each view in the current data model. The first view will be read-only and
           prefixed with the 'view_prefix'. The second view will be writable and have one property that connects to the
           read-only view named 'direct_property'.
        2. It will repeat all connection properties in the new views and update the ValueTypes to match the new views.
        3. Each writable view will have a container with the single property that connects to the read-only view.

        !!! note "Solution Data Model Mode"

            The read-only solution model will only be able to read from the existing containers
            from the enterprise data model, therefore the solution data model will not have
            containers in the solution data model space. Meaning the solution data model views
            will be read-only.

            The write mode will have additional containers in the solution data model space,
            allowing in addition to read through the solution model views, also writing to
            the containers in the solution data model space.

        """
        last_rules = self._state.rule_store.last_verified_rules
        issues = self._state.rule_transform(
            ToSolutionModel(
                new_model_id=data_model_id,
                properties="connection",
                direct_property=direct_property,
                view_prefix=view_prefix,
            )
        )
        if last_rules and not issues.has_errors:
            self._state.last_reference = last_rules
        return issues

    def data_product_model(
        self,
        data_model_id: DataModelIdentifier,
        include: Literal["same-space", "all"] = "same-space",
    ) -> IssueList:
        """Creates a template for a data product model based on the current data model in the session.
        A data product model is only used for reading of instances.
        It can be based on any data model, but typically it is based on an enterprise or solution data model.

        A data product model is a data model that ONLY maps to containers and do not use implements. This is
        typically used for defining the data in a data product.

        What does this function do?
        1. It creates a new view for each view in the current data model. The new views uses the same filter
           as the view it is based on.
        2. It will repeat all connection properties in the new views and update the ValueTypes to match the new views.

        Args:
            data_model_id: The data product data model id that is being created.
            include: The views to include in the data product data model. Can be either "same-space" or "all".
                If you set same-space, only the properties of the views in the same space as the data model
                will be included.
        """
        last_rules = self._state.rule_store.last_verified_rules
        view_ids, container_ids = DMSValidation(
            self._state.rule_store.last_verified_dms_rules
        ).imported_views_and_containers_ids()
        transformers: list[VerifiedRulesTransformer] = []
        client = self._state.client
        if (view_ids or container_ids) and client is None:
            raise NeatSessionError(
                "No client provided. You are referencing unknown views and containers in your data model, "
                "NEAT needs a client to lookup the definitions. "
                "Please set the client in the session, NeatSession(client=client)."
            )
        elif (view_ids or container_ids) and client:
            transformers.append(IncludeReferenced(client, include_properties=True))

        transformers.append(ToDataProductModel(new_model_id=data_model_id, include=include))

        issues = self._state.rule_transform(*transformers)
        if last_rules and not issues.has_errors:
            self._state.last_reference = last_rules
        return issues

    def extension(self, io: Any, output: str | Path | None = None) -> IssueList:
        """Creates a template for an extension of a Cognite model.

        The input is a spreadsheet of a conceptual model in which the concepts are defined
        and marked with the Cognite concept they are extending. For example, if you have a pump
        in the Classes sheet you will see
        ```
        Class: Pump
        Implements: cdf_cdm:CogniteAsset(version=v1)
        ```
        The output will be a spreadsheet in which all the properties from the Cognite concept model
        is added to the spreadsheet. In the example above, the pump concept will have all
        the properties it inherits from the CogniteAsset concept added to the Properties spreadsheet.


        Args:
            io: The input spreadsheet.
            output: The output spreadsheet. If None, the output will be the same
                as the input with `_extension` added to the name.
        """
        ExperimentalFlags.extension.warn()
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        if output is None:
            if isinstance(reader, PathReader):
                output_path = path.with_name(f"{path.stem}_extension{path.suffix}")
            else:
                # The source is not a file, for example, a URL or a stream.
                output_path = Path.cwd() / f"{path.stem}_extension{path.suffix}"
        else:
            output_path = Path(output)

        with catch_issues() as issues:
            read: ReadRules[InformationInputRules] = ExcelImporter(path).to_rules()
            if read.rules is not None:
                # If rules are None there will be issues that are already caught.
                if not isinstance(read.rules, InformationInputRules):
                    raise NeatSessionError(f"The input {reader.name} must contain an InformationInputRules object. ")
                if self._state.client is None:
                    raise NeatSessionError("Client must be set in the session to run the extension.")
                modified = AddCogniteProperties(self._state.client).transform(read)
                if modified.rules is not None:
                    # If rules are None there will be issues that are already caught.
                    info = modified.rules.as_verified_rules()

                    ExcelExporter(styling="maximal").export_to_file(info, output_path)
        issues.action = "Created extension template"
        return issues
