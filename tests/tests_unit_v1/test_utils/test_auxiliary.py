from abc import ABC, abstractmethod

from cognite.neat._utils.auxiliary import get_concrete_subclasses


class GrandParent(ABC):
    @abstractmethod
    def method(self) -> None:
        pass


class Parent(GrandParent, ABC): ...


class Parent2(GrandParent):
    def method(self) -> None:
        print("Parent2 method implementation")


class Child(Parent):
    def method(self) -> None:
        print("Child method implementation")


class Child2(Parent):
    def method(self) -> None:
        print("Child2 method implementation")


class Child3(Child, Parent2):
    def method(self) -> None:
        print("Child3 method implementation")


class Mixin1(ABC):
    @property
    @abstractmethod
    def mixin_property(self) -> str:
        raise NotImplementedError()


class Mixin2(ABC):
    @abstractmethod
    def mixin_method(self) -> str:
        raise NotImplementedError()


class MultiChild(Mixin1, Mixin2, GrandParent):
    def method(self) -> None:
        pass

    def mixin_method(self) -> str:
        return "Mixin method implementation"

    @property
    def mixin_property(self) -> str:
        return "Mixin property implementation"


class TestGetConcreteSubclasses:
    def test_get_concrete_subclasses(self) -> None:
        subclasses = get_concrete_subclasses(GrandParent)

        assert set(subclasses) == {Parent2, Child, Child2, Child3, MultiChild}

    def test_multiple_inheritance(self) -> None:
        subclasses = get_concrete_subclasses(GrandParent)
        assert len(subclasses) == len(set(subclasses)), "Subclasses should be unique"
