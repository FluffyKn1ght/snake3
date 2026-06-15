from datetime import datetime
import json
import time
import traceback
from typing import Any, Callable, Dict

from errors import BadPacketError
from logger import BaseLogger, FileLogger, ForwardLogger, LogLevel, PrintLogger
from network import Packet, PacketID, ProtocolState, SocketHandler


class Snake3Server:
    PROTOCOL_VERSION: int = 775
    """The Minecraft Java protocol version the server speaks."""

    def __init__(self) -> None:
        # TODO: Config and flags

        self.socket_handler: SocketHandler

        self.main_logger: BaseLogger
        try:
            self.main_logger = FileLogger(
                LogLevel.DEBUG, f"{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.log"
            )
        except OSError as e:
            self.main_logger = PrintLogger(LogLevel.DEBUG)
            print(f"Failed to open log file: {e}")
            print("Falling back to console-only logging!! LOG FILE WILL NOT BE SAVED!!")

        self.logger: BaseLogger = ForwardLogger(
            self.main_logger.level, self.main_logger, "Snake3 Server"
        )

        self._running: bool = False

    def run(self) -> None:
        self._running = True

        self.logger.warn("Starting snake3 server...")

        try:
            self.socket_handler = SocketHandler(
                ForwardLogger(
                    self.main_logger.level, self.main_logger, "SocketHandler"
                ),
                "0.0.0.0",
                25565,
                max_recv_size=2**32 - 1,
            )
        except OSError as e:
            self.logger.error(f"Failed to initialize SocketHandler: {e}")
            self.stop()

        self.logger.info("Listening on 0.0.0.0:25565")

        # TODO: Actual console stuff with async command input
        # TODO: Maybe put the SocketHandler onto a different thread?

        while self._running:
            try:
                packets = self.socket_handler.accept_and_recieve()

                for packet in packets:
                    if packet.client.closed:
                        continue

                    try:
                        packet.decode_fields()
                    except BadPacketError as e:
                        if packet.client.state != ProtocolState.HANDSHAKE:
                            self.logger.error(
                                f"Unable to decode packet from {packet.client.addr[0]}:{packet.client.addr[1]}: {e}"
                            )
                        else:
                            self.logger.debug(
                                f"(ignoring) Unable to decode packet from {packet.client.addr[0]}:{packet.client.addr[1]}: {e}"
                            )
                        self.socket_handler.disconnect(packet.client)
                        continue

                    self.logger.debug(f"Got packet: {packet}")

                    try:
                        self.handle_ingoing_packet(packet)
                    except BadPacketError as e:
                        self.logger.error(
                            f"Error while handling packet from {packet.client.addr[0]}:{packet.client.addr[1]}: {e}"
                        )
                        self.socket_handler.disconnect(packet.client)
                    except Exception as e:
                        self.logger.error(
                            f"Exception occured: {e.__class__.__name__}: {e}"
                        )
                        traceback.print_exc()

                time.sleep(0.05)
            except KeyboardInterrupt:
                self.logger.warn("Ctrl+C pressed, stopping server...")
                self.stop()

    def stop(self) -> None:
        self.logger.warn("Stopping server")

        # TODO: stop code

        self._running = False
        self.logger.info("Stopped. See ya! :3")

    def handle_ingoing_packet(self, packet: Packet) -> None:
        """Handles (processes) an ingoing network packet.

        This is mostly a wrapper around the various packet handler
        functions that ensures the packet will be handled correctly.

        Args:
            packet: The packet to process

        Raises:
            BadPacketError - Packet can't be handled (wrong protocol state/no handler/etc)
            (other Exception()s) - Error while handling packet
        """

        """This massive dict is used to define handlers for different packets.

        A packet handler is a Callable that takes a Snake3Server() (self) and the Packet() to
        handle, returning None.

        If a packet doesn't have an entry here, it's considered unimplemented.

        See also network.py/Packet.PACKET_FIELDS

        The structure of the dict is as follows:
            PACKET_HANDLERS[<protocol state of client>][<packet ID>]
        """

        PACKET_HANDLERS: Dict[
            ProtocolState, Dict[PacketID, Callable[[Snake3Server, Packet], None]]
        ] = {
            ProtocolState.HANDSHAKE: {
                PacketID.CLIENT_INTENTION: Snake3Server._handle_packet_intention
            },
            ProtocolState.STATUS: {
                PacketID.CLIENT_STATUS_REQUEST: Snake3Server._handle_packet_status_request,
                PacketID.CLIENT_PING_REQUEST: Snake3Server._handle_packet_ping_request,
            },
            ProtocolState.LOGIN: {
                PacketID.CLIENT_HELLO: Snake3Server._handle_packet_hello
            },
        }

        try:
            PACKET_HANDLERS[packet.client.state][packet.packet_id](self, packet)
        except KeyError:
            raise BadPacketError(
                f"No handler for packet ID {hex(packet.packet_id.value)} for state {packet.client.state.name}"
            )

    def _handle_packet_intention(self, packet: Packet) -> None:
        if (
            packet.fields["intent"].value >= ProtocolState.CONFIGURATION.value
            or packet.fields["intent"].value < ProtocolState.STATUS.value
        ):
            raise BadPacketError("Invalid intent value")
        packet.client.state = ProtocolState(packet.fields["intent"].value)

        self.logger.debug(
            f"[{packet.client.addr[0]}:{packet.client.addr[1]}] Switching to protocol state {packet.client.state.name}"
        )

    def _handle_packet_status_request(self, packet: Packet) -> None:
        status_info: Dict[str, Any] = {
            "version": {
                "name": "yipyipyip :3 *tailwag*",
                "protocol": Snake3Server.PROTOCOL_VERSION,
            },
            "players": {
                "max": 78,
                "online": 26,
                "sample": [
                    {
                        "name": "hiohio                  hiohio",
                        "id": "4566e69f-c907-48ee-8d71-d7ba5aa00d20",
                    },
                    {
                        "name": "      hio            hio",
                        "id": "4566e69f-c907-48ee-8d71-d7ba5aa00d20",
                    },
                    {
                        "name": "       hio         hiohiohio",
                        "id": "4566e69f-c907-48ee-8d71-d7ba5aa00d20",
                    },
                    {
                        "name": "   hio             hio          hio",
                        "id": "4566e69f-c907-48ee-8d71-d7ba5aa00d20",
                    },
                    {
                        "name": "hio                 hio        hio",
                        "id": "4566e69f-c907-48ee-8d71-d7ba5aa00d20",
                    },
                    {
                        "name": "hiohiohio               hiohio",
                        "id": "4566e69f-c907-48ee-8d71-d7ba5aa00d20",
                    },
                ],
            },
            "description": [
                {
                    "text": "yipyipyipyipyipyipyip :3",
                    "color": "gold",
                    "bold": True,
                },
                {
                    "text": "\n(this is all a python script btw-)",
                    "color": "gray",
                    "bold": False,
                },
            ],
            "enforcesSecureChat": False,
        }

        status_json = json.dumps(status_info)

        self.logger.debug(
            f"[{packet.client.addr[0]}:{packet.client.addr[1]}] Responding to status request"
        )
        packet.respond(PacketID.SERVER_STATUS_RESPONSE, status_json=status_json)

    def _handle_packet_ping_request(self, packet: Packet) -> None:
        self.logger.debug(
            f"[{packet.client.addr[0]}:{packet.client.addr[1]}] Responding to ping request"
        )
        packet.respond(
            PacketID.SERVER_PONG_RESPONSE,
            payload=packet.fields["payload"].value,
        )

    def _handle_packet_hello(self, packet: Packet) -> None:
        self.logger.info(
            f"[{packet.client.addr[0]}:{packet.client.addr[1]}] wants to log in as {packet.fields["player_name"].value} ({packet.fields["player_uuid"].value})"
        )

        packet.respond(
            PacketID.SERVER_LOGIN_DISCONNECT,
            reason='{"text":"g","color":"#00FFFF","bold":true,"italic":true}',
        )
