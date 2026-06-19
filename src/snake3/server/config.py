import json
from json.decoder import JSONDecodeError
from typing import Any, Dict, Callable


class BadConfigError(Exception):
    """Gets raised whenever the server encounters an issue when loading a config file."""

    pass


class ServerConfig:
    """Represents a Snake3 server configuration file (config.json)

    Attributes:
        <too many, see attribute descriptions for information>
    """

    LATEST_CONFIG_VERSION: int = 0
    """The latest config version value."""

    def __init__(self) -> None:
        """Creates a blank, default Snake3Config()."""

        self._fpath: str = ""

        # CONFIG FIELDS START BELOW

        self._config_version_DONOTTOUCH: int = ServerConfig.LATEST_CONFIG_VERSION
        """The config version number.

        This value is used only for migrating to newer config versions AND SHOULD NOT BE
        CHANGED BY THE USER to avoid breaking things.

        Latest version number can be obtained from ServerConfig.LATEST_CONFIG_VERSION
        """

        self.listen_address: str = "0.0.0.0"
        """The address the server will listen for incoming connections on.

        This could be 0.0.0.0 for all addresses or 127.0.0.1 for localhost only.

        Default: "0.0.0.0"
        """

        self.listen_port: int = 25565
        """The port the server will listen for incoming connections on.

        The "standard" Minecraft Java port is 25565. This must be in range 0 < port > 65536.

        Default: 25565
        """

        self.log_level: int = 0
        """The default minimal log level for all loggers.

        0 = info, 1 = warn, 2 = error, 3 = fatal. For debug logging, this must be set to 0 *and*
        the server needs to be started with the --debug flag. (Note that this will FLOOD the logs
        with a lot of specific-purpose debug info)

        Default: 0
        """

        self.max_recv_size: int = 4294967295
        """The maximum amount of data the server can recieve from a client at one time.

        Bigger values may increase server load and allow denial-of-service attacks (by sending
        a lot of garbage hard-to-parse data to the server), smaller values may trigger false
        positives. Only adjust this if you're SURE that this is the problem.

        Default: 4294967295 (2^32 - 1)
        """

        self.max_players: int = 20
        """The maximum amount of players that can connect to the server.

        This is a PHYSICAL limit, not just a cosmetic feature.

        Setting this to 0 disables the player limit, "999999" will be shown as the limit instead.

        Default: 20
        """

        self.player_sample_size: int = 10
        """The max amount of players to send in the player sample.

        This is the list of players/text shown when hovering over the online count.

        Setting this to 0 disables the feature.
        """

        self.hide_online_count: bool = False
        """Whether and how to hide the online player count.

        Note that hiding the player count will also hide the player sample.

        Default: False
        """

        self.message_of_the_day: str = "A Snake3 Server"
        """The server description (also known as a message of the day or MOTD).

        This can be either a JSON string or a normal text string. If the value can be JSON-decoded,
        then the decoded JSON object will be sent as a JSON text component; otherwise, it will be sent
        over as-is as a simple text string.

        Default: A Snake3 Server
        """

    @staticmethod
    def load_from_file(fpath: str) -> ServerConfig:
        """Loads a ServerConfig() from a .json file.

        The deserialized JSON object MUST follow the class structure - otherwise, errors will be
        encountered.

        Args:
            fpath: The path to the .json file to load

        Returns:
            The created Snake3Config() object

        Raises:
            BadConfigError - Broken/malformed config (invalid JSON, missing/extra fields, wrong types, etc.)
            OSError - Error opening/loading config file
        """

        # Try to load the config file
        try:
            with open(fpath, "r") as fp:
                config_file_data = json.load(fp)
        except FileNotFoundError:
            config = ServerConfig()
            config._fpath = fpath
            config.save()
            return config
        except JSONDecodeError as e:
            raise BadConfigError(f"JSON decode error: {e}")
        except Exception as e:
            raise OSError(f"Error loading config: {e.__class__.__name__}: {e}")

        # Check version
        try:
            if type(config_file_data["_config_version_DONOTTOUCH"]) is not int:
                raise BadConfigError("Config version is not a number")

            if (
                config_file_data["_config_version_DONOTTOUCH"]
                > ServerConfig.LATEST_CONFIG_VERSION
            ):
                raise BadConfigError(
                    f"Incompatible config version ({config_file_data["_config_version_DONOTTOUCH"]} > {ServerConfig.LATEST_CONFIG_VERSION})"
                )
            elif (
                config_file_data["_config_version_DONOTTOUCH"]
                < ServerConfig.LATEST_CONFIG_VERSION
            ):
                # TODO when newer config versions are needed: check if config can be migrated and
                # attempt migration
                raise BadConfigError("Incorrect config version")
        except KeyError:
            raise BadConfigError(
                'Config doesn\'t have a version (no "_config_version_DONOTTOUCH" field)'
            )

        config = ServerConfig()

        # Load fields
        try:
            for field_name in config.__dict__:
                # ignore _-prefixed fields and functions
                if field_name[0] == "_" or config.__dict__[field_name] is Callable:
                    continue

                if type(config.__dict__[field_name]) != type(
                    config_file_data[field_name]
                ):
                    raise BadConfigError(
                        f"Invalid value for field {field_name}: expected a {type(config.__dict__[field_name])}, got a {type(config_file_data[field_name])}"
                    )

                config.__dict__[field_name] = config_file_data[field_name]
        except KeyError as e:
            raise BadConfigError(f"Missing field: {e}")

        return config

    def save(self) -> None:
        """Saves the ServerConfig() to its associated .JSON file.

        Raises:
            OSError - Error when saving config file
            ValueError - Snake3Config() doesn't have a set file path
        """
        if not self._fpath:
            raise ValueError("No file path set")

        fields: Dict[str, Any] = {}
        for field_name in self.__dict__:
            if field_name[0] == "_" or self.__dict__[field_name] is Callable:
                continue

            fields[field_name] = self.__dict__[field_name]

        fields["_config_version_DONOTTOUCH"] = self._config_version_DONOTTOUCH

        try:
            with open(self._fpath, "w") as fp:
                json.dump(fields, fp, indent=True)
        except Exception as e:
            raise OSError(f"Failed to save config file: {e}")
