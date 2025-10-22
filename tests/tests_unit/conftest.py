from typing import Any

import pytest


@pytest.fixture
def example_dms_data_model_response() -> dict[str, Any]:
    return dict(
        space="my_space",
        externalId="my_data_model",
        version="v1",
        name="My Data Model",
        description="An example data model",
        views=[
            dict(
                space="my_space",
                externalId="MyView",
                version="v1",
            )
        ],
        createdTime=0,
        lastUpdatedTime=1,
        isGlobal=False,
    )
