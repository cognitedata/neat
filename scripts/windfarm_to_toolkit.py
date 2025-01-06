from tests.data import classic_windfarm
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
            filepath.write_text(obj.as_write().dump_yaml())
        else:
            print(f"Skipping {type(obj).__name__} as it does not have a resource folder")


if __name__ == "__main__":
    main()
