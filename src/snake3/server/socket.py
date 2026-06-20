from abc import ABC
from enum import Enum
import socket
from typing import Dict, List, Tuple

from snake3.network.packet import LegacyPing, Packet, ProtocolState
from snake3.network.types import VarNum


class NetworkError(Exception):
    """Gets raised whenever a network error occurs."""

    pass


class SocketConnection:
    """Represents an active socket connection to a client.

    Attributes:
        sock: The underlying client socket
        addr: The client address ([0]) and port ([1])
        state: Current protocol state
        closed: Whether the socket was closed via close() or disconnect()
    """

    def __init__(self, sock: socket.socket, addr: Tuple) -> None:
        self.sock: socket.socket = sock
        self.addr: Tuple = addr
        self.state: ProtocolState = ProtocolState.HANDSHAKE
        self.closed: bool = False

    def close(self) -> None:
        """Closes the SocketConnection(), making it no longer usable.

        This function IMMEDIATELY drops the connection, abruptly disconnecting the client
        with an OS-specific "connection reset" error. It should be used only if the client
        disconnected (to close the socket on the server side) or if it sent something invalid.

        Raises:
            ValueError - SocketConnection() was already closed
        """

        if self.closed:
            raise ValueError("Already closed")

        self.sock.close()
        self.closed = True

    def send(self, data: bytes) -> None:
        """Sends the provided data blob through the SocketConnection().

        If a network error occurs, NetworkError will be raised and the connection will be closed.

        Args:
            data: The data to send to the client

        Raises:
            ValueError: SocketConnection() was closed via close()
            NetworkError: sendall() call failed
        """

        if self.closed:
            raise ValueError("Connection closed")

        try:
            self.sock.sendall(data)
        except Exception as e:
            self.close()
            raise NetworkError(e)


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
        bind_ip: str,
        bind_port: int,
        *args,
        max_recv_size: int,
    ) -> None:
        """Creates and sets up a new SocketHandler.

        Args:
            bind_ip: The IP to bind the server socket to
            bind_port: The port to bind the server socket to

        Kwargs:
            max_recv_size: Maximum amount of data that can be recv()d from a client socket
        """

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

    def accept_and_recieve(self) -> Dict[SocketConnection, List[Packet]]:
        """
        Accepts any new connections and recieves any incoming packets.

        This is like a "process"/"update" function that should be called fairly regularly.
        If a client sends a packet that causes a BadPacketError (i.e. due to a malformed header),
        the client will be promptly disconnected.

        Returns:
            A dict of clients to lists of *partially* parsed packets
        """

        # Accept a connection if one is pending
        try:
            client_sock, client_addr = self.sock.accept()
            client_sock.setblocking(False)
            self.connections.append(SocketConnection(client_sock, client_addr))
            # TODO: Tell that to the server?
        except BlockingIOError:
            pass

        # Recieve any packets from the sockets
        packets: Dict[SocketConnection, List[Packet]] = {}

        for conn in self.connections:
            packets[conn] = []

            data = b""

            while True:
                try:
                    if len(data) > self.max_recv:
                        # Too much data recv()d
                        self.disconnect(conn)
                        break

                    recvd_data = conn.sock.recv(1024)
                    if not recvd_data:
                        # Client disconnected gracefully
                        self.disconnect(conn)
                        break

                    data += recvd_data
                except BlockingIOError:
                    break

            if data:
                offset = 0
                while offset < len(data):
                    try:
                        packet = Packet.create_from_data(data[offset:], False)
                    except ValueError as e:
                        # TODO: log error message
                        self.disconnect(conn)
                        break
                    except LegacyPing:
                        self.disconnect(conn)
                        break

                    packets[conn].append(packet)
                    offset += len(packet.raw)

        return packets

    def disconnect(self, client: SocketConnection) -> None:
        """Disconnects a client from the server.

        Args:
            client: The client to disconnect
        """

        client.close()
        self.connections.remove(client)
        # TODO: Notify server
