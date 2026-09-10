import logging

from scootersim.client import BackendClient
from scootersim.config import Config
from scootersim.runner import run


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    config = Config.from_env()
    logging.getLogger(__name__).info("Simulator config: %s", config)
    client = BackendClient(config.backend_url)
    try:
        run(config, client)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
