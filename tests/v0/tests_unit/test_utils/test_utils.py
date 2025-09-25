import pytest
from cognite.client.exceptions import CogniteDuplicatedError, CogniteReadTimeout

from cognite.neat.v0.core._utils.auxiliary import retry_decorator
from cognite.neat.v0.core._utils.rdf_ import remove_namespace_from_uri


def test_retry_decorator_t1():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test1")
    def timeout_test():
        nonlocal counter
        counter += 1
        if counter == 1:
            raise CogniteReadTimeout()
        elif counter > 1:
            raise CogniteDuplicatedError(duplicated=[1, 2, 3], failed=[], successful=[7, 8, 9])

    with pytest.raises(CogniteDuplicatedError):
        timeout_test()


def test_retry_decorator_t2():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test2")
    def timeout_test():
        nonlocal counter
        counter += 1
        if counter < 2:
            raise CogniteReadTimeout()
        elif counter == 2:
            raise CogniteDuplicatedError(duplicated=[1, 2, 3], failed=[], successful=[])

    timeout_test()


def test_retry_decorator_t3():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test3")
    def timeout_test():
        nonlocal counter
        counter += 1
        if counter < 3:
            raise CogniteReadTimeout()
        elif counter == 3:
            raise CogniteDuplicatedError(duplicated=[1, 2, 3], failed=[], successful=[])

    timeout_test()


def test_retry_decorator_t4():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test4")
    def timeout_test():
        nonlocal counter
        counter += 1
        raise CogniteReadTimeout()

    with pytest.raises(CogniteReadTimeout):
        timeout_test()


def test_retry_decorator_t5():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test5")
    def timeout_test():
        nonlocal counter
        counter += 1
        if counter < 4:
            raise Exception("test5")

    timeout_test()


def test_remove_namespace():
    assert remove_namespace_from_uri(
        ["http://www.example.org/index.html#section2", "http://www.example.org/index.html#section3"]
    ) == ["section2", "section3"]
    assert remove_namespace_from_uri("www.example.org/index.html#section2") == "www.example.org/index.html#section2"
    assert remove_namespace_from_uri("all/hope/is#lost") == "all/hope/is#lost"
