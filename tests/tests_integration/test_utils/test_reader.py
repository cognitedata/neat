from cognite.neat._utils.reader import NeatReader


class TestHttpFileReader:
    def test_read_text(self) -> None:
        reader = NeatReader.create("https://apps-cdn.cogniteapp.com/toolkit/publicdata/valhall_file_metadata.csv")

        assert reader.exists()

        text = reader.read_text()
        assert text.startswith("name,source,mime_type")
