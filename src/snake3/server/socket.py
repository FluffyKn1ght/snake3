from abc import ABC
from enum import Enum
import socket
from typing import Dict, List, Tuple

from snake3.network.packet import Packet, ProtocolState
from snake3.network.types import VarNum


class SocketConnection:
    """Represents an active socket connection to a client.

    Attributes:
        sock: The client socket
        addr: The client address ([0]) and port ([1])
        state: Current protocol state
    """

    def __init__(self, sock: socket.socket, addr: Tuple) -> None:
        self.sock: socket.socket = sock
        self.addr: Tuple = addr
        self.state: ProtocolState = ProtocolState.HANDSHAKE


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
                        self.disconnect(conn, "Too much data recieved!")
                        break

                    recvd_data = conn.sock.recv(1024)
                    if not recvd_data:
                        self.disconnect(conn, "Disconnected")
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
                        self.disconnect(conn, f"Invalid packet ({e})")
                        break

                    packets[conn].append(packet)
                    offset += len(packet.raw)

        return packets

    def disconnect(
        self, client: SocketConnection, reason: str = "Disconnected by server"
    ) -> None:
        """Disconnects a client from the server.

        This should only be called for server-side disconnects - client-side disconnects are
        to be processed manually.

        Args:
            client: The client to disconnect
        """

        client.sock.close()
        self.connections.remove(client)
        # TODO: Notify server
