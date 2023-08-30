from pathlib import Path

# we should make this a proper package that loads examples
# similar how they handle it in xarray:
# https://github.com/pydata/xarray/blob/main/xarray/tutorial.py
# Currently there are simple paths to the examples which are then easily loaded in the notebooks

power_grid_model = Path(__file__).parent / "power-grid-example.xlsx"
simple_example = Path(__file__).parent / "sheet2cdf-transformation-rules.xlsx"
source_to_solution_mapping = Path(__file__).parent / "source-to-solution-mapping-rules.xlsx"
nordic44 = Path(__file__).parent / "Rules-Nordic44-to-TNT.xlsx"
nordic44_graphql = Path(__file__).parent / "Rules-Nordic44-to-graphql.xlsx"
