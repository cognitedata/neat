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


def get_children(
    element: Element, child_tag: str, ignore_namespace: bool = False, no_children: int = -1
) -> Element | list[Element]:
    """Get children of an XML element.

    Args:
        element: XML element to get children from.
        child_tag: Tag of the children to get.
        ignore_namespace: bool that decides if wildcard * should be used to ignore namespace of children elements tag
        no_children: Max number of children to get. Defaults to -1 (all).

    Returns:
        List of XML elements if no_children > 1, otherwise XML element.
    """
    if ignore_namespace:
        children = element.findall(f".//{{*}}{child_tag}")
    else:
        children = element.findall(f".//{child_tag}")
    return children[:no_children] if no_children > 0 else children
