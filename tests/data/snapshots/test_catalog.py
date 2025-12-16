from typing import get_args

from .catalog import CDF_SNAPSHOTS_DIR, LOCAL_SNAPSHOTS_DIR, CDFScenario, LocalScenario


class TestCatalog:
    def test_local_scenario_is_up_to_date(
        self,
    ) -> None:
        literal_scenario = get_args(LocalScenario)
        local_scenarios = [p.name for p in LOCAL_SNAPSHOTS_DIR.iterdir() if p.is_dir()]

        assert set(literal_scenario) == set(local_scenarios)

    def test_cdf_scenario_is_up_to_date(
        self,
    ) -> None:
        literal_scenario = get_args(CDFScenario)
        cdf_scenarios = [p.name for p in CDF_SNAPSHOTS_DIR.iterdir() if p.is_dir()]

        assert set(literal_scenario) == set(cdf_scenarios)
