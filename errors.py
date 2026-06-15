class BadPacketError(Exception):
    """Gets raised whenever an error occurs when decoding an incoming packet."""

    pass


class LegacyPing(Exception):
    """Gets raised whenever a client tries to perform a legacy server list ping. (b"\xfe\x01\xfa...")"""

    pass


class BadConfigError(Exception):
    """Gets raised whenever the server encounters an issue when loading a config file."""

    pass
