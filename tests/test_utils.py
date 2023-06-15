from cognite.client.exceptions import CogniteDuplicatedError, CogniteReadTimeout

from cognite.neat.core.utils import retry_decorator


def test_retry_decorator_t1():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test1")
    def timeout_test():
        nonlocal counter
        counter += 1
        print(counter)
        if counter == 1:
            raise CogniteReadTimeout()
        elif counter == 2:
            raise CogniteDuplicatedError(duplicated=[1, 2, 3], failed=[], successful=[7, 8, 9])

    try:
        timeout_test()
    except Exception as e:
        assert isinstance(e, CogniteDuplicatedError)


def test_retry_decorator_t2():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test2")
    def timeout_test():
        nonlocal counter
        counter += 1
        print(counter)
        if counter == 1:
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
        print(counter)
        if counter >= 1 and counter <= 2:
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

    with pytest.raises(CogniteReadTimeout)
        timeout_test()


def test_retry_decorator_t5():
    counter = 0

    @retry_decorator(max_retries=4, retry_delay=0, component_name="test5")
    def timeout_test():
        nonlocal counter
        counter += 1
        print(counter)
        raise Exception("test5")

    try:
        timeout_test()
    except Exception as e:
        assert isinstance(e, Exception)
        assert counter == 5
