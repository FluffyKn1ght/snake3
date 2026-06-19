from enum import Enum
import json
import re
import struct
from tkinter.constants import N
from typing import Any, Dict, List, Tuple
import uuid
from importlib import resources

from snake3.network.types import VarNum


class ProtocolState(Enum):
    """Represents different states of the Minecraft Java protocol"""

    UNKNOWN = "#unknown#"
    """Protocol state is not known"""

    HANDSHAKE = "handshake"
    """Client connected but no Handshake packet was sent yet"""

    STATUS = "status"
    """Server list ping"""

    LOGIN = "login"
    """Client wants to actually join the server, i.e. "Join Server" pressed"""

    CONFIGURATION = "configuration"
    """Client is talking to the server to establish configuration stuff before playing"""

    PLAY = "play"
    """Client is ingame, having connected and configured itself with the server"""


class PacketFieldType(Enum):
    """Represents different types of packet fields."""

    NULL = "null"
    """Placeholder/invalid value, not in protocol spec.

    Encoding/decoding this will always raise a ValueError.
    """

    BOOL = "bool"
    """Boolean True/False value, 0x00 or 0x01."""

    BYTE = "byte"
    """Signed byte, stores a number from -128 to 127

    Supports enums.
    """

    UBYTE = "ubyte"
    """Unsigned byte, stores a number from 0 to 255

    Supports enums.
    """

    SHORT = "short"
    """Signed short int, stores a number from -32768 to 32767

    Supports enums.
    """

    USHORT = "ushort"
    """Unsigned short int, stores a number from 0 to 65535

    Supports enums.
    """

    INT = "int"
    """Signed int, stores a number from -2147483648 to 2147483647

    Supports enums.
    """

    LONG = "long"
    """Signed long int, stores a number from -9223372036854775808 to 9223372036854775807"""

    FLOAT = "float"
    """Single-precision IEEE 754 floating point number"""

    DOUBLE = "double"
    """Double-precision IEEE 754 floating point number"""

    STRING = "string"
    """UTF-8 encoded string data, prefixed with its byte length as a VarInt.

    Some subtypes require a "max_length" field. (actual byte length limit is (n*3)+3)

    Subtypes:
        "plain": Plain text string with normal content
        "json": Stringified JSON. Strings with this subtype MUST decode to a JSON object, otherwise, an
        error will be raised on decoding. Max length is ALWAYS 32767.
        "identifier": Identifier string (i.e. "minecraft:yippity_yip"). Checked against regex patterns to ensure
        proper content. Max length is ALWAYS 32767.
    """

    VARINT = "varint"
    """Variable-size 32-bit signed int.

    Supports enums.
    """

    VARLONG = "varlong"
    """Variable-size 64-bit signed int"""

    UUID = "uuid"
    """A UUID. Encoded as a 128-bit integer (most significant 64, least significant 64)"""

    STRUCT = "struct"
    """Multi-field complex data struct.

    Subtypes:
        The name of the PacketFieldStruct contained in the value, for use with PacketFieldSturct.TEMPLATES
        (i.e. "GameProfile")
    """

    # TODO: Add all of the other types


class PacketField:
    """Represents a data field of a Packet().

    Attributes:
        type: The basic type of the packet field. This might sometimes be too generic to go off of in code.
        subtype: Additional type information, "" if it doesn't apply to the type.
            (i.e. struct name for PacketFieldType.STRUCT or "plain"/"json"/etc. for PacketFieldType.STRING)
        max_length: Maximum length of the encoded content, None if it doesn't apply to the type. Units depend
        on the specific type.
        enum: A list of accepted values, mostly used for enums (duh). [] if not used by field.
        value: The value stored in the field.

    """

    IDENTIFIER_NAMESPACE_REGEX: re.Pattern = re.compile("[a-z0-9.-_]")
    """A compiled regex expression used to check namespaces of identifier strings.

    (the "minecraft" part of "minecraft:yippity_yip")
    """

    IDENTIFIER_VALUE_REGEX: re.Pattern = re.compile("[a-z0-9.-_/]")
    """A compiled regex expression used to check values of identifier strings.

    (the "yippity_yip" part of "minecraft:yippity_yip")
    """

    def __init__(self) -> None:
        """Creates a new blank PacketField."""

        self.type: PacketFieldType = PacketFieldType.NULL
        self.subtype: str = ""
        self.max_length: int | None = None
        self.enum: List[Any] = []
        self.value: Any = None

    @staticmethod
    def from_json(json_obj: Dict[str, Any]) -> PacketField:
        """Creates a new PacketField configured with the data from the provided JSON object.

        Args:
            json_obj: The JSON object to get config data from.

        Returns:
            The created PacketField, with a default non-None value set

        Raises:
            ValueError - Provided JSON object is invalid
        """

        field: PacketField = PacketField()

        field.type = PacketFieldType(json_obj["type"])

        try:
            field.subtype = json_obj["subtype"]
        except KeyError:
            pass

        try:
            field.max_length = json_obj["max_length"]
        except KeyError:
            pass

        try:
            field.enum = json_obj["enum"]
        except KeyError:
            pass

        return field

    def fill_in(self, from_data: bytes) -> int:
        """Fills in the PacketField() with data from the provided blob, returning the amount of data consumed.

        This will fill in the field ONCE and then stop, returning the amount of data consumed, which can be
        added to an offset counter to parse multiple back-to-back to fields (see Packet().decode_fields())

        This operation is NOT ATOMIC, the PacketField() should be discarded if this errors out.

        Args:
            from_data: The data blob to take data from

        Returns:
            The amount of data consumed, in bytes

        Raises:
            ValueError - Something went wrong while decoding packet field
        """

        match self.type:
            case PacketFieldType.NULL:
                raise ValueError("Attempted to fill in a NULL-type field")
            case PacketFieldType.BOOL:
                if from_data[0] == 0x00:
                    self.value = False
                elif from_data[1] == 0x01:
                    self.value = True
                else:
                    raise ValueError(
                        f"Invalid value for BOOL field: {hex(from_data[0])}"
                    )

                if self.enum:
                    self._enum_check()
                return 1
            case PacketFieldType.BYTE:
                try:
                    self.value = struct.unpack("!b", from_data[0:1])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking BYTE: {e}")

                if self.enum:
                    self._enum_check()
                return 1
            case PacketFieldType.UBYTE:
                try:
                    self.value = struct.unpack("!B", from_data[0:1])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking UBYTE: {e}")

                if self.enum:
                    self._enum_check()
                return 1
            case PacketFieldType.SHORT:
                try:
                    self.value = struct.unpack("!h", from_data[0:2])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking SHORT: {e}")

                if self.enum:
                    self._enum_check()
                return 2
            case PacketFieldType.USHORT:
                try:
                    self.value = struct.unpack("!H", from_data[0:2])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking USHORT: {e}")

                if self.enum:
                    self._enum_check()
                return 2
            case PacketFieldType.INT:
                try:
                    self.value = struct.unpack("!i", from_data[0:4])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking INT: {e}")

                if self.enum:
                    self._enum_check()
                return 4
            case PacketFieldType.LONG:
                try:
                    self.value = struct.unpack("!i", from_data[0:8])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking LONG: {e}")

                if self.enum:
                    self._enum_check()
                return 8
            case PacketFieldType.FLOAT:
                try:
                    self.value = struct.unpack("!f", from_data[0:4])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking FLOAT: {e}")

                return 4
            case PacketFieldType.DOUBLE:
                try:
                    self.value = struct.unpack("!d", from_data[0:8])[0]
                except struct.error as e:
                    raise ValueError(f"Error unpacking DOUBLE: {e}")

                return 8
            case PacketFieldType.STRING:
                # Decode length
                try:
                    string_length, string_length_size = VarNum.decode(from_data, False)
                except (ValueError, EOFError) as e:
                    raise ValueError(f"Error decoding string length varint: {e}")

                # Ensure length limit
                match self.subtype:
                    case "plain":
                        if self.max_length is not None:
                            if string_length > (self.max_length * 3) + 3:
                                raise ValueError(
                                    f"String is too long ({string_length} but limit is {self.max_length})"
                                )
                        else:
                            raise ValueError("No max_length specified")
                    case "json":
                        if string_length > 32767:
                            raise ValueError("String is too long (limit is 32767)")
                    case "identifier":
                        if string_length > 32767:
                            raise ValueError("String is too long (limit is 32767)")
                    case _:
                        raise ValueError(f"Invalid string subtype {self.subtype}")

                # Decode contents
                try:
                    self.value = from_data[
                        string_length_size : string_length + 1
                    ].decode("utf-8")
                except UnicodeDecodeError as e:
                    raise ValueError(f"Error decoding string: {e}")

                # Validate contents
                match self.subtype:
                    case "json":
                        try:
                            json_obj = json.loads(self.value)
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Invalid JSON string: {e}")
                    case "identifier":
                        # Regex patterns courtesy of Minecraft Wiki:
                        # https://minecraft.wiki/w/Java_Edition_protocol/Packets#Identifier
                        ident_content = self.value.split(":")
                        if len(ident_content) == 1:
                            # Check just the value if no namespace was provided
                            if not re.fullmatch(
                                PacketField.IDENTIFIER_VALUE_REGEX, ident_content[0]
                            ):
                                raise ValueError("Invalid identifier: bad value")
                        elif len(ident_content) == 2:
                            # Check both namespace and value if namespace WAS provided
                            if not re.fullmatch(
                                PacketField.IDENTIFIER_NAMESPACE_REGEX, ident_content[0]
                            ):
                                raise ValueError("Invalid identifier: bad namespace")
                            if not re.fullmatch(
                                PacketField.IDENTIFIER_VALUE_REGEX, ident_content[1]
                            ):
                                raise ValueError("Invalid identifier: bad value")
                        else:
                            # There shouldn't be any more parts to a valid identifier
                            raise ValueError('Invalid identifier: too many ":"s ')

                return string_length + string_length_size
            case PacketFieldType.VARINT:
                try:
                    varint, varint_size = VarNum.decode(from_data, False)
                except ValueError | EOFError as e:
                    raise ValueError(f"Error decoding VarInt: {e}")
                self.value = varint

                if self.enum:
                    self._enum_check()
                return varint_size
            case PacketFieldType.VARLONG:
                try:
                    varlong, varlong_size = VarNum.decode(from_data, True)
                except ValueError | EOFError as e:
                    raise ValueError(f"Error decoding VarLong: {e}")
                self.value = varlong

                return varlong_size
            case PacketFieldType.UUID:
                self.value = uuid.UUID(bytes=from_data[0:16])
                return 16
            case PacketFieldType.STRUCT:
                raise ValueError("PacketFieldStruct() isn't implemented yet")
            case _:
                return 0

    def _enum_check(self) -> None:
        if self.value in self.enum:
            return
        else:
            raise ValueError(
                f"Invalid enum value {self.value}: valid values are {self.enum}"
            )


class Packet:
    """Represents a Minecraft Java protocol packet.

    Attributes:
        name: The official packet name as per MC datagen output.
            This is "#unknown#" by default, unless set by Packet().decode_fields() or an external function.
        state: The ProtocolState the packet was recieved in.
            This is ProtocolState.UNKNOWN by default, unless set by Packet().decode_fields() or an external
            function.
        clientbound: Whether the packet is clientbound (True) or serverbound (False).
            This is None by default, unless set by Packet().decode_fields() or an external function.
        fields: The Python-accesible representation of packet data.
            This is None by default, unless populated by an external function or Packet().decode_fields().
        length: The length of the packet *as per protocol spec* (packet ID + data).
            This is -1 by default, unless the packet was made using Packet.create_from_data() or was
            encoded with Packet().encode_fields().
        id: The packet ID integer. THIS DOES NOT TELL YOU WHAT THE PACKET IS, use Packet().name,
            Packet().state and Packet().clientbound instead.
            This is -1 by default, unless the packet was made using Packet.create_from_data() or was
            encoded with Packet().encode_fields().
        data: The unparsed data of the packet.
            This is always uncompressed, even if created from/encoded to compressed data.
            This in empty unless the packet was created using Packet.create_from_data() or was encoded for
            sending using Packet().encode_fields().
        raw: The raw packet representation used on-the-wire.
            This in empty unless the packet was created using Packet.create_from_data() or was encoded for
            sending using Packet().encode_fields().
            Note that this can sometimes be compressed and not plainly readable.
    """

    PACKET_FIELDS: Dict[str, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]] = (
        json.loads(
            resources.files("snake3")
            .joinpath("data")
            .joinpath("packet-fields.json")
            .read_text()
        )
    )
    """Contains important information about which packets have which fields.

    Loaded from snake3/data/packet-fields.json
    """

    PACKET_IDS: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = json.loads(
        resources.files("snake3")
        .joinpath("mcdata")
        .joinpath("server-reports")
        .joinpath("packets.json")
        .read_text()
    )
    """Contains packet ID to packet name mappings.

    This file is extracted from the Minecraft Java server data generator upon installing Snake3
    and thus is licensed under the Minecraft EULA.
    (TODO: make the package setup script extract this by running a server jar automatically)

    Loaded from snake3/mcdata/server-reports/packets.json
    """

    def __init__(self) -> None:
        """Creates a new empty packet."""

        self.name: str = "#unknown#"
        self.state: ProtocolState = ProtocolState.UNKNOWN
        self.clientbound: bool | None = None
        self.fields: Dict[str, PacketField] | None = None
        self.length: int = -1
        self.id: int = -1
        self.data: bytes = b""
        self.raw: bytes = b""

    @staticmethod
    def create_from_data(data: bytes, compressed: bool) -> Packet:
        """Creates a packet from raw data.

        Note that this only partially parses the packet, properties such as Packet().name **will not be set**
        unless you run Packet().decode_fields() with the correct arguments after creating the packet.

        This creates ONE packet, even if the data blob has multiple packets back-to-back.

        Args:
            data: The data to create the packet from
            bool: Whether the packet is expected to be in the compressed format or not

        Returns:
            The created Packet()

        Raises:
            ValueError - The provided packet has an invalid header or is otherwise corrupted/malformed
        """

        packet: Packet = Packet()

        if compressed:
            raise ValueError("Compression support isn't implemented yet")
        else:
            try:
                length, length_size = VarNum.decode(data, False)

                packet.length = length
                packet.raw = data[: length + length_size]

                id, id_size = VarNum.decode(packet.raw[length_size:], False)
                packet.id = id

                packet.data = packet.raw[length_size + id_size :]
            except Exception as e:
                raise ValueError(e)

        return packet

    def decode_fields(self, state: ProtocolState, clientbound: bool) -> None:
        """Determines and decodes the data fields of the packet.

        This function requires you to provide additional context about the packet - the
        protocol state in which it was obtained and whether it's a clientbound or serverbound
        packet.

        This function also sets Packet().name and Packet().fields, making the packet properly
        readable in Python.

        This function is NOT ATOMIC and can incompletely decode the packet in case of an exception.
        It's not recommended to use the Packet() after this function raises an exception!

        Args:
            state: The ProtocolState during which the packet was recieved.
            clientbound: Whether the packet was clientbound (True) or serverbound (False).

        Raises:
            ValueError - Failed to decode one of the packet fields
            TypeError - Packet is unrecognized (invalid ID, invalid state, etc.)
        """

        self.clientbound = clientbound

        try:
            packet_names: Dict[str, Dict[str, int]] = Packet.PACKET_IDS[state.value][
                "clientbound" if self.clientbound else "serverbound"
            ]

            for packet_name in packet_names:
                if packet_names[packet_name]["protocol_id"] == self.id:
                    self.name = packet_name
                    break
        except KeyError:
            raise TypeError(
                f"Unrecognized {"clientbound" if self.clientbound else "serverbound"} packet ID {self.id} for state {state.value}"
            )

        try:
            packet_field_info: Dict[str, Dict[str, Any]] = Packet.PACKET_FIELDS[
                state.value
            ]["clientbound" if self.clientbound else "serverbound"][self.name]
        except KeyError:
            raise TypeError(
                f"Unrecognized {"clientbound" if self.clientbound else "serverbound"} packet {self.name} (ID {self.id}) for state {state.value}"
            )

        self.fields = {}

        offset: int = 0
        for field_name in packet_field_info:
            field: PacketField = PacketField.from_json(packet_field_info[field_name])
            offset += field.fill_in(self.data[offset:])

            self.fields[field_name] = field
