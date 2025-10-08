from rdflib import Dataset


class Instances(Dataset):
    """A subclass of rdflib.Dataset with additional functionalities:

    Instantiation such as:
    - in-memory
    - in-memory oxigraph
    - on-disk oxigraph
    - remote sparql endpoint

    as well as holding standard queries for the dataset split into:
    - select
    - update

    """

    ...
