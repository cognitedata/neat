import yaml

from tests.v0.data import classic_windfarm
from pathlib import Path
from cognite.client.data_classes._base import WriteableCogniteResource
from cognite_toolkit._cdf_tk.loaders import RESOURCE_LOADER_LIST
from cognite_toolkit._cdf_tk.utils import to_directory_compatible
THIS_FOLDER = Path(__file__).resolve(strict=True).parent
MODULE = THIS_FOLDER / "integration_runner" / "modules" / 'test_data' / "windfarm"

LOADER_BY_RESOURCE_TYPE = {
    loader.resource_cls: loader for loader in RESOURCE_LOADER_LIST
}

def main() -> None:
    data_set_external_id_by_id = {item.id: item.external_id for item in classic_windfarm.DATASETS}
    asset_external_id_by_id = {item.id: item.external_id for item in classic_windfarm.ASSETS}
    obj: WriteableCogniteResource
    for obj in [
        *classic_windfarm.DATASETS,
        *classic_windfarm.ASSETS,
        *classic_windfarm.EVENTS,
        *classic_windfarm.FILES,
        *classic_windfarm.TIME_SERIES,
        *classic_windfarm.RELATIONSHIPS,
        *classic_windfarm.SEQUENCES,
        classic_windfarm.SEQUENCE_ROWS,
        *classic_windfarm.LABELS,
    ]:
        loader = LOADER_BY_RESOURCE_TYPE.get(type(obj))
        if loader:
            if hasattr(obj, "external_id"):
                external_id = to_directory_compatible(obj.external_id)
                filepath = MODULE/ loader.folder_name / f"{external_id}.{loader.kind}.yaml"
            else:
                raise NotImplementedError
            filepath.parent.mkdir(exist_ok=True, parents=True)
            dumped = obj.as_write().dump(camel_case=True)
            if data_set_id := dumped.pop("dataSetId", None):
                dumped["dataSetExternalId"] = data_set_external_id_by_id[data_set_id]
            if asset_ids := dumped.pop("assetIds", None):
                dumped["assetExternalIds"] = [asset_external_id_by_id[asset_id] for asset_id in asset_ids]
            if asset_id := dumped.pop("assetId", None):
                dumped["assetExternalId"] = asset_external_id_by_id[asset_id]
            dumped.pop("parentId", None)
            filepath.write_text(yaml.safe_dump(dumped, sort_keys=False))
        else:
            print(f"Skipping {type(obj).__name__} as it does not have a resource folder")


if __name__ == "__main__":
    main()
