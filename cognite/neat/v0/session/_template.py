from pathlib import Path
from typing import Any, Literal

from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat.v0.core._constants import BASE_MODEL
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.exporters import ExcelExporter
from cognite.neat.v0.core._data_model.importers import ExcelImporter
from cognite.neat.v0.core._data_model.models import UnverifiedConceptualDataModel
from cognite.neat.v0.core._data_model.models._base_verified import RoleTypes
from cognite.neat.v0.core._data_model.models.physical import PhysicalValidation
from cognite.neat.v0.core._data_model.transformers import (
    AddCogniteProperties,
    IncludeReferenced,
    ToDataProductModel,
    ToEnterpriseModel,
    VerifiedDataModelTransformer,
)
from cognite.neat.v0.core._issues import IssueList, catch_issues
from cognite.neat.v0.core._utils.reader import NeatReader, PathReader
from cognite.neat.v0.session._experimental import ExperimentalFlags

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
        last_dm = self._state.data_model_store.last_verified_data_model
        issues = self._state.data_model_transform(
            ToEnterpriseModel(
                new_model_id=data_model_id,
                org_name=org_name,
                dummy_property=dummy_property,
                move_connections=True,
            )
        )
        if last_dm and not issues.has_errors:
            self._state.last_reference = last_dm
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
        last_dm = self._state.data_model_store.last_verified_data_model
        view_ids, container_ids = PhysicalValidation(
            self._state.data_model_store.last_verified_physical_data_model
        ).imported_views_and_containers_ids()
        transformers: list[VerifiedDataModelTransformer] = []
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

        issues = self._state.data_model_transform(*transformers)
        if last_dm and not issues.has_errors:
            self._state.last_reference = last_dm
        return issues

    def conceptual_model(
        self,
        io: Any,
        base_model: BASE_MODEL = "CogniteCore",
        total_concepts: int | None = None,
    ) -> None:
        """This method will create a template for a conceptual data modeling

        Args:
            io: file path to the Excel sheet
            base_model: The base model to use for implements in the conceptual data model.
                        Currently only supporting CogniteCore.
            total_concepts: The total number of concepts to provide in implements for selection.
                         Default is None, meaning all concepts will be provided.

        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()

        ExcelExporter(base_model=base_model, total_concepts=total_concepts).template(RoleTypes.information, path)

    def expand(self, io: Any, output: str | Path | None = None, dummy_property: str = "GUID") -> IssueList:
        """Creates a template for an extension of a Cognite model by expanding properties from CDM.

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
            dummy_property: The dummy property to use as placeholder for user-defined properties
                for each user-defined concept, and to alleviate need for usage of filters in
                physical data model. When converting a data model, it is recommended to have at least
                one property for each concept. This ensures that you follow that recommendation.
        """
        ExperimentalFlags.extension.warn()
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        if output is None:
            if isinstance(reader, PathReader):
                output_path = path.with_name(f"{path.stem}_expand{path.suffix}")
            else:
                # The source is not a file, for example, a URL or a stream.
                output_path = Path.cwd() / f"{path.stem}_expand{path.suffix}"
        else:
            output_path = Path(output)

        with catch_issues() as issues:
            read: ImportedDataModel[UnverifiedConceptualDataModel] = ExcelImporter(path).to_data_model()
            if read.unverified_data_model is not None:
                # If data model arise None there will be issues that are already caught.
                if not isinstance(read.unverified_data_model, UnverifiedConceptualDataModel):
                    raise NeatSessionError(
                        f"The input {reader.name} must contain an UnverifiedConceptualDataModel object. "
                    )
                if self._state.client is None:
                    raise NeatSessionError("Client must be set in the session to run the extension.")
                modified = AddCogniteProperties(self._state.client, dummy_property).transform(read)
                if modified.unverified_data_model is not None:
                    # If data model is None there will be issues that are already caught.
                    info = modified.unverified_data_model.as_verified_data_model()

                    ExcelExporter(styling="maximal").export_to_file(info, output_path)
        issues.action = "Created extension template"

        # Adding issues to the state in the data model store
        if issues:
            self._state.data_model_store._last_issues = issues
        return issues
