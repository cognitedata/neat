from pathlib import Path

# we should make this a proper package that loads examples
# similar how they handle it in xarray:
# https://github.com/pydata/xarray/blob/main/xarray/tutorial.py
# Currently there are simple paths to the examples which are then easily loaded in the notebooks

_EXAMPLES = Path(__file__).parent

power_grid_model = _EXAMPLES / "power-grid-example.xlsx"
power_grid_containers = _EXAMPLES / "power-grid-containers.yaml"
power_grid_data_model = _EXAMPLES / "power-grid-model.yaml"
simple_example = _EXAMPLES / "sheet2cdf-transformation-rules.xlsx"
source_to_solution_mapping = _EXAMPLES / "source-to-solution-mapping-rules.xlsx"
nordic44 = _EXAMPLES / "Rules-Nordic44-to-TNT.xlsx"
nordic44_graphql = _EXAMPLES / "Rules-Nordic44-to-graphql.xlsx"
skos = _EXAMPLES / "skos-rules.xlsx"
wind_energy_ontology = _EXAMPLES / "wind-energy.owl"
