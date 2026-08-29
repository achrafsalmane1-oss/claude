"""Application logging."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("leadmaps")


def configure_logging(debug: bool = False) -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
