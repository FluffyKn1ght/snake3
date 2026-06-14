class Uninstantiatable:
    """A class that *always* throws a TypeError on instantiation.

    This class is meant to be a parent to utility classes, like network/DataTypeHandler.
    """

    def __init__(self) -> None:
        raise TypeError(f"{__class__.__name__} is an uninstantiatable class")
