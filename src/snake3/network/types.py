from typing import Tuple

from snake3.misc import Uninstantiateable


class VarNum(Uninstantiateable):
    """Utility class that handles encoding/decoding VarInt/VarLong values"""

    @staticmethod
    def decode(data: bytes, is_varlong: bool) -> Tuple[int, int]:
        """Decodes a VarInt/VarLong from bytes into an int.

        Args:
            data: The serialized VarNum data
            is_varlong: If true, treats the VarNum as a 64-bit VarLong instead of a 32-bit VarInt

        Returns:
            The decoded VarNum ([0]) and its length in bytes ([1])

        Raises:
            ValueError - Invalid data
            EOFError - Continue bit set but EOF was reached
        """

        i = 0
        position = 0
        result = 0
        for byte in data:
            result |= (byte & 0x7F) << position
            if not (byte & 0x80):
                break
            elif i >= len(data) - 1:
                raise EOFError("Continue bit set but EOF was reached")
            position += 7
            i += 1
            if (not is_varlong and position >= 32) or (is_varlong and position >= 64):
                raise ValueError("VarNum is too big")

        # Correctly interpret sign bit
        bits = 64 if is_varlong else 32

        result &= (1 << bits) - 1
        if result & (1 << (bits - 1)):
            return (result - (1 << bits), i + 1)

        return (result, i + 1)

    @staticmethod
    def encode(num: int, is_varlong: bool) -> bytes:
        """Encodes an int into a VarInt/VarLong.

        Args:
            num: The number to encode into a VarNum
            is_varlong: If true, the resulting VarNum will be a VarLong (64-bit) instead of a VarInt (32-bit)

        Returns:
            The encoded VarNum data

        Raises:
            ValueError - Resulting number data is too big
        """
        out = bytearray()

        mask = 0xFFFFFFFFFFFFFFFF if is_varlong else 0xFFFFFFFF
        num &= mask

        while True:
            if num <= 0x7F:
                out.append(num & 0x7F)
                break

            out.append(num & 0x7F | 0x80)

            num = (num >> 7) & mask

        if (is_varlong and len(out) > 10) or (not is_varlong and len(out) > 5):
            raise ValueError("Resulting VarNum data is too big")

        return bytes(out)
