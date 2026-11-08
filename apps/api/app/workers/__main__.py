"""Standalone worker: `python -m app.workers` (run with WORKER_MODE=external on the API)."""

from __future__ import annotations

import logging
import signal
import time

from ..core import config
from .outbox import drain

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("reclaim.worker")
_stop = False


def _on_signal(*_):
    global _stop
    _stop = True


def main() -> None:
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    log.info("worker started")
    while not _stop:
        try:
            if drain() == 0:
                time.sleep(config.settings.worker_poll_seconds)
        except Exception:
            log.exception("worker loop error")
            time.sleep(5)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
