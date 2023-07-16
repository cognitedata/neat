from pathlib import Path

# we should make this a proper package that loads examples
# similar how they handle it in xarray:
# https://github.com/pydata/xarray/blob/main/xarray/tutorial.py
# Currently there are simple paths to the examples which are then easily loaded in the notebooks

power_grid_model = Path(__file__).parent / "rules" / "power-grid-example.xlsx"
power_grid_graph_sheet = Path(__file__).parent / "graph-sheets" / "power-grid-example.xlsx"
