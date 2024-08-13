from collections.abc import Generator
from xml.etree.ElementTree import Element

from lxml.etree import QName


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


def split_element_tag_namespace(element: Element) -> tuple[str, str]:
    """Split namespace and tag of an XML element.

    Args:
        element: XML element to extract namespace and tag from.

    Returns: Instance of ElementTag with tag and namespace.

    Example:

    >>> split_element_tag_namespace("{http://www.example.org/index.html}section2")
    ('section2', 'http://www.example.org/index.html')

    """
    resource = QName(element.tag)
    return (resource.localname, resource.namespace)
