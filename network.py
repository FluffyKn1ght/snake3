from abc import ABC
from enum import Enum
import socket
import struct
from typing import Any, Dict, List, Tuple

from datatypes import VarNum
from errors import BadPacketError, LegacyPing
from logger import BaseLogger


class ProtocolState(Enum):
    """Represents different states of the Minecraft Java protocol"""

    HANDSHAKE = 0
    """Client connected but no Handshake packet was sent yet"""

    STATUS = 1
    """Server list ping"""

    LOGIN = 2
    """Client wants to actually join the server, i.e. "Join Server" pressed"""

    TRANSFER = 3
    """Client is transferring from another server ("Reconfiguring..." screen)"""

    CONFIGURATION = 4
    """Client is talking to the server to establish configuration stuff before playing"""

    PLAY = 5
    """Client has connected and configured"""


class PacketID(Enum):
    """Represents different packet ID values.

    Note that some packet ID values may have multiple names (i.e. both INTENTION,
    STATUS_REQUEST and STATUS_RESPONSE have a value of 0x00). Which name should be
    used depends on the client's protocol state as well as whether the packet is
    clientbound (outgoing) or serverbound (ingoing).

    SERVER_ packet ID names are for outgoing packets, CLIENT_ packet ID names are for
    ingoing packets. This is to prevent collisions (HELLO is both a Login Start packet
    sent by the client and an Encryption Request packet sent by the server).

    TODO: Move this to a seperate file that will be generated based on Minecraft server
    data registry output! (hardcoding this does not expand the dong)
    """

    UNKNOWN = -1
    """Invalid packet ID"""

    # Handshaking
    CLIENT_INTENTION = 0x00

    # Status
    CLIENT_STATUS_REQUEST = 0x00
    SERVER_STATUS_RESPONSE = 0x00
    CLIENT_PING_REQUEST = 0x01
    SERVER_PONG_RESPONSE = 0x01


class PacketFieldType(Enum):
    """Represents different types of packet fields.

    The underlying values used here are arbitrary and don't correspond to anything.
    """

    NULL = -1
    """Placeholder/invalid value, not in protocol spec"""

    BOOL = 0
    """Boolean True/False value, 0x00 or 0x01."""

    BYTE = 1
    """Signed byte, stores a number from -128 to 127"""

    UBYTE = 2
    """Unsigned byte, stores a number from 0 to 255"""

    SHORT = 3
    """Signed short int, stores a number from -32768 to 32767"""

    USHORT = 4
    """Unsigned short int, stores a number from 0 to 65535"""

    INT = 5
    """Signed int, stores a number from -2147483648 to 2147483647"""

    LONG = 7
    """Signed long int, stores a number from -9223372036854775808 to 9223372036854775807"""

    FLOAT = 8
    """Single-precision IEEE 754 floating point number"""

    DOUBLE = 9
    """Double-precision IEEE 754 floating point number"""

    STRING = 10
    """UTF-8 encoded string, prefixed with its byte length. Requires a length value to signify the length
    limit (actual limit is (n*3)+3 bytes)"""

    TEXT_COMPONENT = 11
    """Text component. Encoded as a String/Compound NBT tag."""

    JSON_TEXT_COMPONENT = 12
    """Same as TEXT_COMPONENT, but JSON-encoded."""

    IDENTIFIER = 13
    """String with max length of 32767"""

    VARINT = 14
    """Variable-size 32-bit signed int"""

    VARLONG = 15
    """Variable-size 64-bit signed int"""

    # TODO: Add all of the other types


class PacketField:
    """Represents a field of a Minecraft Java protocol packet

    Attributes:
        type (PacketFieldType): The type of the field
        value (Any): The value of the field. If no value should be set for the field this is None.
        length (int | None): The length of the field. If type has constant length this will be None.
    """

    def __init__(
        self, field_type: PacketFieldType, value: Any = None, length: int | None = None
    ) -> None:
        """Creates a new packet field.

        Args:
            field_type: The type of the field
            value: The value of the field. If no value should be set for the field this should None.
            length: The length of the field. If type has constant length this should be None.
        """

        self.type: PacketFieldType = field_type
        self.value: Any = value
        self.length: int | None = length

    def __str__(self) -> str:
        return f"<PacketField: {self.type.name}({self.length}) {self.value}>"

    def decode(self, data: bytes) -> int:
        """Decodes a value into the PacketField(), returning its size in bytes.

        This function will stop once one value is decoded and then store that value in
        the PacketField().

        Args:
            data: The data to decode

        Returns:
            The size of the decoded value, in bytes.

        Raises:
            TypeError: Type set for field can't be decoded (i.e. NULL type or unimplemented)
            ValueError: Provided data is invalid
            EOFError: Provided data ends unexpectedly
        """

        match self.type:
            case PacketFieldType.NULL:
                raise TypeError("Can't decode NULL type field")
            case PacketFieldType.BOOL:
                if len(data) < 1:
                    raise EOFError(
                        f"Expected at least 1 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                if data[0] == 0x01:
                    self.value = True
                elif data[0] == 0x00:
                    self.value = False
                else:
                    raise ValueError(
                        f"Unknown value {hex(data[0])} for bool field (expected 0x00/0x01)"
                    )
                return 1
            case PacketFieldType.BYTE:
                if len(data) < 1:
                    raise EOFError(
                        f"Expected at least 1 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    self.value = struct.unpack("!b", data[:1])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 1
            case PacketFieldType.UBYTE:
                if len(data) < 1:
                    raise EOFError(
                        f"Expected at least 1 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    self.value = struct.unpack("!B", data[:1])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 1
            case PacketFieldType.SHORT:
                if len(data) < 2:
                    raise EOFError(
                        f"Expected at least 2 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    self.value = struct.unpack("!h", data[:2])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 2
            case PacketFieldType.USHORT:
                if len(data) < 2:
                    raise EOFError(
                        f"Expected at least 2 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    self.value = struct.unpack("!H", data[:2])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 2
            case PacketFieldType.INT:
                if len(data) < 4:
                    raise EOFError(
                        f"Expected at least 4 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )
                try:
                    self.value = struct.unpack("!i", data[0:4])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 4
            case PacketFieldType.LONG:
                if len(data) < 8:
                    raise EOFError(
                        f"Expected at least 8 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )
                try:
                    self.value = struct.unpack("!q", data[0:8])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 8
            case PacketFieldType.FLOAT:
                if len(data) < 4:
                    raise EOFError(
                        f"Expected at least 4 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )
                try:
                    self.value = struct.unpack("!f", data[:4])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 4
            case PacketFieldType.DOUBLE:
                if len(data) < 8:
                    raise EOFError(
                        f"Expected at least 8 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )
                try:
                    self.value = struct.unpack("!d", data[:8])[0]
                except struct.error as e:
                    raise ValueError(f"struct.unpack() failed with {e}")

                return 8
            case PacketFieldType.STRING:
                # TODO: Move this to datatypes.py

                if len(data) < 1:
                    raise EOFError(
                        f"Expected at least 1 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    length, length_size = VarNum.decode(data, False)
                except ValueError as e:
                    raise ValueError(
                        f"Failed to decode string length: VarNum.decode() failed with {e}"
                    )

                if len(data) - length_size < length:
                    raise EOFError(
                        f"Expected length of {length} bytes, got {len(data) - length_size} instead"
                    )

                if self.length:
                    if len(data) > (self.length * 3) + 3:
                        raise ValueError("String is too long")

                self.value = data[length_size : length + 1].decode(encoding="utf-8")

                return length_size + length
            case PacketFieldType.VARINT:
                if len(data) < 1:
                    raise EOFError(
                        f"Expected at least 1 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    result, result_size = VarNum.decode(data, False)
                except ValueError as e:
                    raise ValueError(f"VarNum.decode() failed with {e}")
                except EOFError as e:
                    raise ValueError(f"VarNum.decode() failed with {e}")

                self.value = result

                return result_size
            case PacketFieldType.VARLONG:
                if len(data) < 1:
                    raise EOFError(
                        f"Expected at least 1 bytes for {self.type.name} field (got {len(data)} bytes instead)"
                    )

                try:
                    result, result_size = VarNum.decode(data, True)
                except ValueError as e:
                    raise ValueError(f"VarNum.decode() failed with {e}")
                except EOFError as e:
                    raise ValueError(f"VarNum.decode() failed with {e}")

                self.value = result

                return result_size
            case _:
                raise TypeError(
                    f"No decoder implemented for field type {self.type.name}"
                )

    def encode(self) -> bytes:
        """Encodes a PacketField() into its on-the-wire form.

        Returns:
            The encoded PacketField(), as bytes

        Raises:
            TypeError: Type set for field can't be encoded (i.e. NULL type or unimplemented)
            ValueError: Provided field data is invalid and can't be properly encoded
        """

        result = b""

        match self.type:
            # TODO: Implement the remaining types
            case PacketFieldType.NULL:
                raise TypeError("Can't encode NULL type field")
            case PacketFieldType.STRING:
                try:
                    result += VarNum.encode(len(self.value), False)
                except ValueError as e:
                    raise ValueError(
                        f"Failed to encode string length: VarNum.encode() failed with {e}"
                    )

                result += self.value.encode("utf-8")
                # TODO: IMPORTANT! Check that string fits in size limit
            case PacketFieldType.LONG:
                result += struct.pack("!q", self.value)
            case _:
                raise TypeError(
                    f"Can't encode field of type {self.type.name} (unimplemented)"
                )

        return result


class Packet:
    """Represents a Minecraft Java protocol packet

    Attributes:
        client (SocketConnection): The client associated with the packet
        outgoing (bool): If True, packet is from the server; if False, packet is from the client
        packet_id (PacketID): The ID of the packet, essentially its type.*
        fields (Dict[str, PacketField]): The parsed data fields of the packet.*
        length (int): The length of the packet *as per protocol spec* (packet ID + data).**
        data (bytes): The unparsed data of the packet.**
        raw (bytes): The raw packet data.**

        *Packet must be an outgoing packet or have been decoded with Packet().decode_fields()
        **Packet must be an ingoing pakcet or have been encoded with Packet().encode_fields()
    """

    _PACKET_FIELDS: Dict[
        ProtocolState, Dict[str, Dict[PacketID, Dict[str, PacketField]]]
    ] = {
        ProtocolState.HANDSHAKE: {
            "serverbound": {
                PacketID.CLIENT_INTENTION: {
                    "protocol_version": PacketField(PacketFieldType.VARINT),
                    "server_address": PacketField(PacketFieldType.STRING, None, 255),
                    "server_port": PacketField(PacketFieldType.USHORT),
                    "intent": PacketField(PacketFieldType.VARINT),
                }
            }
        },
        ProtocolState.STATUS: {
            "serverbound": {
                PacketID.CLIENT_STATUS_REQUEST: {},
                PacketID.CLIENT_PING_REQUEST: {
                    "payload": PacketField(PacketFieldType.LONG)
                },
            },
            "clientbound": {
                PacketID.SERVER_STATUS_RESPONSE: {
                    "status_json": PacketField(PacketFieldType.STRING, None, 32767)
                },
                PacketID.SERVER_PONG_RESPONSE: {
                    "payload": PacketField(PacketFieldType.LONG)
                },
            },
        },
    }

    def __init__(self, client: SocketConnection, outgoing: bool) -> None:
        """Creates a new socket packet.

        This is meant to be used only internally in the class, Packet.create_ingoing() and
        Packet.create_outgoing() should be used to create Packet()s instead.

        Args:
            client: The client associated with the packet
            outgoing: If True, packet is from the server; if False, packet is from the client
        """

        super().__init__()

        self.client: SocketConnection = client
        self.outgoing: bool = outgoing

        self.packet_id: PacketID = PacketID.UNKNOWN
        self.fields: Dict[str, PacketField] = {}
        self.length: int = 0
        self.data: bytes = b""
        self.raw: bytes = b""

        self._full_length: int = 0

    def __str__(self) -> str:
        return f"<Packet: {hex(self.packet_id.value)}, {self.client.addr[0]}:{self.client.addr[1]}, {"clientbound" if self.outgoing else "serverbound"}, {self.length} ({self._full_length}) bytes>"

    @staticmethod
    def create_ingoing(client: SocketConnection, raw: bytes) -> Packet:
        """Creates a new ingoing Packet from recieved data.

        This *partially* decodes the packet, reading the length from the header.
        For a complete deserialization, Packet().decode_fields() should be called.

        This function creates ONE packet, discarding any data that doesn't fit into it.
        Data recieved from the socket should instead be handed over to Packet.create_ingoing_from_recvd(),
        which will create multiple packets if needed.

        Args:
            client: The client who sent the packet
            raw: The raw packet data

        Returns:
            The parsed incoming packet

        Raises:
            BadPacketError - Packet header structure is invalid
            LegacyPing - Packet is a legacy ping (b"\xfe\x01\xfa...")
        """

        packet = Packet(client, False)
        packet.raw = raw

        # print(packet.raw)

        # Check if the client trying to connect is pre-1.6
        # Probably not the best way to do it but hey, all we need to do after this is
        # to close the connection (not even send a server MOTD/status)
        if packet.raw[0:3] == b"\xfe\x01\xfa":
            raise LegacyPing("Client is attempting a legacy ping")

        # Decode packet header info
        try:
            length, length_size = VarNum.decode(packet.raw, False)
        except ValueError as e:
            raise BadPacketError(
                f"Failed to decode packet length: VarNum.decode() failed with {e}"
            )
        except EOFError as e:
            raise BadPacketError(
                f"Unexpected EOF decoding packet length (malformed packet?): {e}"
            )

        packet.length = length
        packet._full_length = length_size + length

        try:
            packet_id, packet_id_size = VarNum.decode(packet.raw[length_size:], False)
        except ValueError as e:
            raise BadPacketError(
                f"Failed to decode packet ID: VarNum.decode() failed with {e}"
            )
        except EOFError as e:
            raise BadPacketError(
                f"Unexpected EOF decoding packet ID (malformed packet?): {e}"
            )

        try:
            packet.packet_id = PacketID(packet_id)
        except ValueError:
            raise BadPacketError(f"Unknown packet ID {hex(packet_id)}")

        packet.data = packet.raw[length_size + packet_id_size : length + 1]

        return packet

    @staticmethod
    def create_ingoing_from_recvd(client: SocketConnection, raw: bytes) -> List[Packet]:
        """Creates ingoing packets from raw data recv()d from a client socket.

        This is somewhat of a wrapper around Packet.create_ingoing().

        Args:
            client: The client who sent the packet
            raw: The raw recv()d data

        Returns:
            A list of created Packet()s

        Raises:
            BadPacketError - Packet structure of one of the packets is invalid
        """

        packets: List[Packet] = []
        i = 0

        while i < len(raw):
            packet = Packet.create_ingoing(client, raw[i:])
            i += packet._full_length
            packets.append(packet)

        return packets

    @staticmethod
    def create_outgoing(
        client: SocketConnection, packet_id: PacketID, *args, **fields
    ) -> Packet:
        """Creates a new outgoing Packet with the specified packet ID and fields.

        Args:
            client: The client the packet is meant for
            packet_id: The ID of the created packet

        Kwargs:
            **fields - The values to be applied to the fields

        Returns:
            The created outgoing packet

        Raises:
            ValueError - **fields keys don't match packet fields for the specified ID
        """

        packet = Packet(client, True)
        packet.packet_id = packet_id

        template = Packet._PACKET_FIELDS[client.state]["clientbound"][packet_id]
        if list(template.keys()) != list(fields.keys()):
            raise ValueError("Provided fields don't match packet template")

        for field_name in template:
            packet.fields[field_name] = PacketField(
                template[field_name].type,
                fields[field_name],
                template[field_name].length,
            )

        return packet

    def decode_fields(self) -> None:
        """Decode the packet data.

        This function will populate Packet().fields based on the packet ID and the client's
        current protocol state.

        Raises:
            BadPacketError - Error while decoding one or more fields
        """

        # Acquire the correct template for the packet ID
        try:
            template = Packet._PACKET_FIELDS[self.client.state]["serverbound"][
                self.packet_id
            ]
        except KeyError:
            raise BadPacketError(
                f"Unknown ingoing packet ID {hex(self.packet_id.value)} for protocol state {self.client.state.name}"
            )

        # Parse the fields
        offset = 0
        for field_name in template:
            field = template[field_name]
            self.fields[field_name] = PacketField(field.type, None, field.length)
            try:
                offset += self.fields[field_name].decode(self.data[offset:])
            except ValueError as e:
                raise BadPacketError(
                    f"Error while decoding packet field {field_name} ({field.type.name}): {e}"
                )
            except EOFError as e:
                raise BadPacketError(
                    f"Unexpected EOF while decoding packet field {field_name} ({field.type.name}) (malformed packet?): {e}"
                )

    def encode_fields(self) -> None:
        """Encodes the packet fields into raw binary data, preparing the packet for sendoff.

        Raises:
            BadPacketError - Error while encoding packet
        """

        # Encode the individual field data
        for field_name in self.fields:
            try:
                self.data += self.fields[field_name].encode()
            except ValueError as e:
                raise BadPacketError(
                    f"Failed to encode field {field_name} ({self.fields[field_name].type.name}): {e}"
                )
            except TypeError as e:
                raise BadPacketError(
                    f"Can't encode fields of type {self.fields[field_name].type.name}: {e}"
                )

        # Generate and encode the packet header
        try:
            encoded_packet_id = VarNum.encode(self.packet_id.value, False)
        except ValueError as e:
            raise BadPacketError(f"Error while encoding packet ID: {e}")

        self.length = len(encoded_packet_id) + len(self.data)

        try:
            encoded_length = VarNum.encode(self.length, False)
        except ValueError as e:
            raise BadPacketError(f"Error while encoding packet length: {e}")

        self.raw = encoded_length + encoded_packet_id + self.data

    def respond(self, response_packet_id: PacketID, *args, **kwargs) -> None:
        """Respond to the packet with another packet.

        Args:
            response_packet_id: The packet ID of the response packet

        Kwargs:
            **fields - The values to be applied to the fields (as in Packet().create_outgoing())

        Raises:
            ValueError - **fields keys don't match packet fields for the specified ID
            BadPacketError - Error while encoding response packet
        """

        response_packet = Packet.create_outgoing(
            self.client, response_packet_id, **kwargs
        )
        response_packet.encode_fields()
        response_packet.client.send_packet(response_packet)


class SocketConnection:
    """Represents an active socket connection to a client.

    Attributes:
        sock (socket.socket): The client socket
        addr (Tuple): The client address ([0]) and port ([1])
        state (ProtocolState): Current protocol state
    """

    def __init__(self, sock: socket.socket, addr: Tuple) -> None:
        self.sock: socket.socket = sock
        self.addr: Tuple = addr
        self.state: ProtocolState = ProtocolState.HANDSHAKE

    def close(self):
        """Closes the SocketConnection().

        This function completely closes the client socket, meaning no data
        can be sent or recieved after this call. This should only be called
        after an error in the connection (e.g. a bad packet) or after the
        client is ready to gracefully disconnect.
        """

        self.sock.close()

    def send_packet(self, packet: Packet) -> None:
        """Sends a packet to the client through the SocketConnection().

        Args:
            packet: The packet to send
        """

        # print(packet.raw)
        self.sock.sendall(packet.raw)


class SocketHandler:
    """An object that handles sockets and packets

    Attributes:
        logger: The logger that will be used by the SocketHandler
        bind_ip: The IP the server socket is bound to
        bind_port: The port the server socket is bound to
        max_recv_size: Maximum amount of data that can be recv()d from a client socket
    """

    def __init__(
        self,
        logger: BaseLogger,
        bind_ip: str,
        bind_port: int,
        *args,
        max_recv_size: int,
    ) -> None:
        """Creates and sets up a new SocketHandler.

        Args:
            logger: The logger that will be used by the SocketHandler
            bind_ip: The IP to bind the server socket to
            bind_port: The port to bind the server socket to

        Kwargs:
            max_recv_size: Maximum amount of data that can be recv()d from a client socket
        """

        self.logger: BaseLogger = logger

        self.bind_ip: str = bind_ip
        self.bind_port: int = bind_port

        self.max_recv: int = max_recv_size

        self.sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Enable port reusage
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Disable buffering (Nagle's algorhithm)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Enable keepalive checks
        # self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # Make socket non-blocking
        self.sock.setblocking(False)

        self.sock.bind((self.bind_ip, self.bind_port))
        self.sock.listen()

        self.connections: List[SocketConnection] = []

    def accept_and_recieve(self) -> List[Packet]:
        """
        Accepts any new connections and recieves any incoming packets.

        This is like a "process"/"update" function that should be called fairly regularly.
        If a client sends a packet that causes a BadPacketError (i.e. due to a malformed header),
        the client will be promptly disconnected.

        Returns:
            A list of *partially* parsed packets
        """

        # Accept a connection if one is pending
        try:
            client_sock, client_addr = self.sock.accept()
            client_sock.setblocking(False)
            self.connections.append(SocketConnection(client_sock, client_addr))
            # TODO: Tell that to the server?
            self.logger.debug(f"[{client_addr[0]}:{client_addr[1]}] Connected")
        except BlockingIOError:
            pass

        # Recieve any packets from the sockets
        packets: list[Packet] = []

        for conn in self.connections:
            data = b""

            while True:
                try:
                    if len(data) > self.max_recv:
                        # Too much data recieved
                        # TODO: tell server we're not doing this shi?
                        self.logger.error(
                            f"[{conn.addr[0]}:{conn.addr[1]}] sock.recv() overflow (client sent too much data or server/network is lagging REALLY bad)"
                        )
                        self.disconnect(conn)
                        break

                    recvd_data = conn.sock.recv(1024)
                    if not recvd_data:
                        # Other side closed connection
                        # TODO: tell that to the server?
                        # conn.close()
                        self.logger.debug(
                            f"[{conn.addr[0]}:{conn.addr[1]}] Disconnected (other side closed connection)"
                        )
                        # specifically not call SocketHandler().disconnect()
                        self.connections.remove(conn)
                        conn.sock.close()
                        break

                    data += recvd_data
                except BlockingIOError:
                    break

            if data:
                try:
                    packets += Packet.create_ingoing_from_recvd(conn, data)
                except BadPacketError as e:
                    # TODO: tell server the client done f'd up?
                    self.logger.error(
                        f"[{conn.addr[0]}:{conn.addr[1]}] Malformed packet header: {e}"
                    )
                    self.disconnect(conn)
                except LegacyPing:
                    self.disconnect(conn)

        return packets

    def disconnect(self, client: SocketConnection) -> None:
        """Disconnects a client from the server.

        This should only be called for server-side disconnects - client-side disconnects are
        to be processed manually.

        Args:
            client: The client to disconnect
        """

        self.logger.debug(f"[{client.addr[0]}:{client.addr[1]}] Disconnected by server")
        client.close()
        self.connections.remove(client)
