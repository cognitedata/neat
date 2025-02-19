from cognite.neat import NeatSession, get_cognite_client
from typing import cast



client = get_cognite_client(".env")

# lst_models= client.data_modeling.spaces.list(limit=-1)
# print(lst_models)

neat = cast(NeatSession, NeatSession(client))
neat.read.cfihos.from_config_definitions("cfihos_src/config.yaml")
