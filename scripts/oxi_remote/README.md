# OXIGRAPH as a "remote" graph database

This is a simple example of how to use OXIGRAPH as a "remote" graph database. The idea is to have a server running OXIGRAPH and a client that connects to it. The client can be any programming language that supports HTTP requests, but in this example we use Neat.


## Running the server

Make empty folder "data" in the same directory as [./docker-compose.yaml](./docker-compose.yaml) prior running:

```
docker-compose up
```

Access the OXIGRAPH web interface at http://localhost:7878

Two main endpoints are available:
- `http://localhost:7878/query` for running queries
- `http://localhost:7878/update` for updates of the graph

More details: https://github.com/oxigraph/oxigraph/tree/main/cli



## How to connect to the server and set new NeatGraphStore for instances


```
from cognite.neat.v0.core._store import NeatGraphStore
from cognite.neat import NeatSession


# Assumes that the server runs on localhost port 7878
store = NeatGraphStore.from_oxi_remote_store(endpoint_url="http://localhost:7878")

neat = NeatSession()

# While we are experimenting Oxi remote store this is the way to set it
neat._state.instances._store = store

# use the neat session as usual, e.g.:
neat.read.examples.nordic44()

```