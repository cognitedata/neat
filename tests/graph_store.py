import time

import pandas as pd

from cognite.neat.graph.stores import NeatGraphStore, RdfStoreType

pd.options.display.max_colwidth = 100

gs = NeatGraphStore()
gs.init_graph(
    RdfStoreType.GRAPHDB,
    "http://localhost:7200/repositories/tnt-solution",
    "http://localhost:7200/repositories/tnt-solution/statements",
)

query = "SELECT ?instance ?prop ?value WHERE { ?instance rdf:type <http://purl.org/cognite/tnt/Terminal> . \
         ?instance ?prop ?value . } order by ?instance limit 100 "
start = time.perf_counter()
r_df = gs.query_and_save_to_cache(query)
stop = time.perf_counter()
print("Query DF Elapsed time :" + str(stop - start))

start = time.perf_counter()
grouped_df = r_df.groupby("instance")
stop = time.perf_counter()
print("Groupby Elapsed time :" + str(stop - start))
print("Get group Elapsed time :" + str(stop - start))
counter = 0
for name, group in grouped_df:
    print(name)
    print(group.filter(items=["property", "value"]).values.tolist())
    counter += 1
    if counter % 1000 == 0:
        print(counter)
