import contextlib
import io

from cognite.neat import NeatSession


def test_plugin_error_handling():
    """Test that the plugin API raises the correct error when no plugin is found."""
    neat = NeatSession()

    # Neat Session does not raise an error, but prints it.
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        neat.plugins.data_model.read("csv", "./test.txt")

    printed_statements = output.getvalue()
    assert printed_statements == (
        "[ERROR] PluginError: No plugin of type 'DataModelImporterPlugin' registered \nunder name 'csv'\n"
    )
