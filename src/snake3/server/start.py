from snake3.server.config import ServerConfig, BadConfigError
from snake3.server.server import Snake3Server


def main() -> int:
    try:
        config: ServerConfig = ServerConfig.load_from_file("config.json")
    except BadConfigError as e:
        print(f"ERROR: Failed to parse config.json: {e}")
        return 1
    except OSError as e:
        print(f"ERROR: Failed to load config.json: {e}")
        return 1

    server: Snake3Server = Snake3Server(config=config)
    server.start()

    return 0


if __name__ == "__main__":
    main()
