import base64
from datetime import datetime
import json
import time
import traceback
import os
from pathlib import Path
from typing import Any, Callable, Dict
from importlib.metadata import version

from snake3.network.packet import Packet, ProtocolState
from snake3.server.config import ServerConfig
from snake3.server.logging import (
    BaseLogger,
    FileLogger,
    ForwardLogger,
    LogLevel,
    PrintLogger,
)
from snake3.server.socket import SocketConnection, SocketHandler


class Snake3Server:
    PROTOCOL_VERSION: int = 775
    """The Minecraft Java protocol version the server speaks."""

    MC_VERSION: str = "1.21.10"
    """The Minecraft Java version the server was made for. Purely cosmetic."""

    def __init__(self, *args, config: ServerConfig) -> None:
        self.config: ServerConfig = config

        self.socket_handler: SocketHandler

        # TODO: Handle loglevel config field
        self.main_logger: BaseLogger
        try:
            Path("logs").mkdir(parents=True, exist_ok=True)

            self.main_logger = FileLogger(
                LogLevel.DEBUG,
                f"logs/{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.log",
            )
        except OSError as e:
            self.main_logger = PrintLogger(LogLevel.DEBUG)
            print(f"Failed to open log file: {e}")
            print("Falling back to console-only logging!! LOG FILE WILL NOT BE SAVED!!")

        self.logger: BaseLogger = ForwardLogger(
            self.main_logger.level, self.main_logger, self.__class__.__name__
        )

        self._running: bool = False

    def start(self) -> None:  # TODO: Handle loglevel config field
        self._running = True

        self.logger.warn(
            f"Starting {self.__class__.__name__} version {self.__class__.MC_VERSION} ({self.__class__.PROTOCOL_VERSION})..."
        )

        try:
            self.socket_handler = SocketHandler(
                self.config.listen_address,
                self.config.listen_port,
                max_recv_size=self.config.max_recv_size,
            )
        except OSError as e:
            self.logger.error(f"Failed to initialize SocketHandler: {e}")
            self.stop()

        self.logger.info(
            f"Listening on {self.config.listen_address}:{self.config.listen_port}"
        )

        # TODO: Actual console stuff with async command input
        # TODO: Maybe put the SocketHandler onto a different thread?

        while self._running:
            try:
                packets = self.socket_handler.accept_and_recieve()

                for client in packets:
                    for packet in packets[client]:
                        try:
                            packet.decode_fields(client.state, False)
                        except (ValueError, TypeError) as e:
                            if client.state != ProtocolState.HANDSHAKE:
                                self.logger.error(
                                    f"Unable to decode packet from {client.addr[0]}:{client.addr[1]}: {e}"
                                )
                            else:
                                self.logger.debug(
                                    f"(ignoring) Unable to decode packet from {client.addr[0]}:{client.addr[1]}: {e}"
                                )
                            self.socket_handler.disconnect(client)
                            break

                        try:
                            self.handle_ingoing_packet(packet, client)
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

    def handle_ingoing_packet(self, packet: Packet, client: SocketConnection) -> None:
        """Handles (processes) an ingoing network packet.

        This is mostly a wrapper around the various packet handler
        functions that ensures the packet will be handled correctly.

        Args:
            packet: The packet to process
            client: The SocketConnection() to associate this packet with

        Raises:
            (various Exception()s) - Error while handling packet
        """

        self.logger.debug(f"{packet.raw} {client.addr}")
        if packet.fields:
            for field_name in packet.fields:
                self.logger.debug(
                    f"{field_name} {packet.fields[field_name].type} {packet.fields[field_name].value}"
                )
