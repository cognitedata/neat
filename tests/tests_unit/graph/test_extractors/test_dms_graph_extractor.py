from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat._graph.extractors import DMSGraphExtractor
from tests.data import car


class TestDMSGraphExtractor:
    def test_extract_car_example(self) -> None:
        with monkeypatch_cognite_client() as client:
            extractor = DMSGraphExtractor(car.CAR_MODEL, client)

            triple_count = len(list(extractor.extract()))
            info_rules = extractor.get_information_rules()
            dms_rules = extractor.get_dms_rules()

        expected_info = car.get_care_rules()
        assert triple_count == len(car.TRIPLES)
        assert {cls_.class_ for cls_ in info_rules.classes} == {cls_.class_ for cls_ in expected_info.classes}
        assert {view.view.external_id for view in dms_rules.views} == {view.external_id for view in car.CAR_MODEL.views}
