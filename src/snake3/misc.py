class Uninstantiateable:
    """A class that will always raise a TypeError on instantiation."""

    def __init__(self) -> None:
        raise TypeError("Can't instantiate this class")
