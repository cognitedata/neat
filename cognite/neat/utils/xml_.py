from collections.abc import Generator
from xml.etree.ElementTree import Element


def iterate_tree(node: Element, skip_root: bool = False) -> Generator:
    """Iterate over all elements in an XML tree.

    Args:
        node: XML tree to iterate over.

    Returns:
        Generator of XML elements.
    """
    if not skip_root:
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


def remove_element_tag_namespace(element_tag: str) -> str:
    """Remove namespace prefix from tag of an XML element.

    Args:
        element: XML element to extract namespace and tag from.

    Returns: The element tag as a string

    Example:

    >>> remove_element_tag_namespace("{http://www.example.org/index.html}section2")
    'section2'
    """
    return element_tag.split("}", 1)[1]
