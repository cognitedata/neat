from abc import abstractmethod
from collections.abc import Iterable

from cognite.neat.graph.models import Triple
from cognite.neat.utils.auxiliary import get_classmethods


class BaseExtractor:
    """This is the base class for all extractors. It defines the interface that
    extractors must implement.
    """

    @abstractmethod
    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()

    @classmethod
    def _repr_html_(cls) -> str:
        if cls.__doc__:
            docstring = cls.__doc__.split("Args:")[0].strip().replace("\n", "<br />")
        else:
            docstring = "Missing Description"
        factory_methods = get_classmethods(cls)
        if factory_methods:
            factory_methods_str = "".join(f"<li>{m.__name__}</li>" for m in factory_methods)
            docstring += (
                f"<br /><strong>Factory Methods:</strong><br />"
                f'<ul style="list-style-type:circle;">{factory_methods_str}</ul>'
            )
        return f"<h3>{cls.__name__}</h3><p>{docstring}</p>"
