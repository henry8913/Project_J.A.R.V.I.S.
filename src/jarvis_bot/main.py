from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv

from .config import Settings
from .service import JarvisTelegramService


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    load_dotenv()
    settings = Settings()
    settings.ensure_directories()
    settings.validate_required_secrets()
    configure_logging(settings.log_level)
    service = JarvisTelegramService(settings=settings)
    asyncio.run(service.run_polling())


if __name__ == "__main__":
    main()
