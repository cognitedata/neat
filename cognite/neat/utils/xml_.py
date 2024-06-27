from collections.abc import Generator
from xml.etree.ElementTree import Element


def iterate_tree(node: Element) -> Generator:
    """Iterate over all elements in an XML tree.

    Args:
        node: XML tree to iterate over.

    Returns:
        Generator of XML elements.
    """
    yield node
    for child in node:
        yield from iterate_tree(child)


def get_children(element: Element, child_tag: str, no_children: int = -1) -> list[Element]:
    """Get children of an XML element.

    Args:
        element: XML element to get children from.
        child_tag: Tag of the children to get.
        no_children: Max number of children to get. Defaults to -1 (all).

    Returns:
        List of XML elements if no_children > 1, otherwise XML element.
    """
    children = []
    for child in element:
        if child.tag == child_tag:
            if no_children == 1:
                return [child]
            else:
                children.append(child)
    return children
