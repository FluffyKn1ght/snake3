from config import Snake3Config
from errors import BadConfigError
from server import Snake3Server


def main() -> None:
    try:
        config: Snake3Config = Snake3Config.load_from_file("config.json")
    except BadConfigError as e:
        print(f"ERROR: Failed to parse config file: {e}")
        return
    except OSError as e:
        print(f"ERROR: Failed to load config file: {e}")
        return

    server: Snake3Server = Snake3Server(config=config)
    server.run()


if __name__ == "__main__":
    main()
