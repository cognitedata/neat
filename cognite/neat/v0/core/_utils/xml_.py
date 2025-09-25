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
    element: Element,
    child_tag: str,
    include_nested_children: bool = False,
    ignore_namespace: bool = False,
    no_children: int = -1,
) -> Element | list[Element]:
    """Get direct children of an XML element.

    Args:
        element: XML element to get children from.
        child_tag: Tag of the children to get.
        include_nested_children: bool to decide if only direct child elements should be extracted, or if all child
        elements (including nested ones) should be returned.
        ignore_namespace: bool that decides if wildcard * should be used to ignore namespace of children elements tag
        no_children: Max number of children to get. Defaults to -1 (all).

    Returns:
        List of XML elements if no_children > 1, otherwise XML element.
    """
    search_string = ""
    if ignore_namespace:
        if include_nested_children:
            search_string = f".//{{*}}{child_tag}"
        else:
            search_string = f".{{*}}{child_tag}"
    elif not ignore_namespace:
        if include_nested_children:
            search_string = f".//{child_tag}"
        else:
            search_string = f".{child_tag}"
    children = element.findall(search_string)
    return children[:no_children] if no_children > 0 else children
