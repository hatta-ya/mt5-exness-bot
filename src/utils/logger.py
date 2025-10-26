import logging
import os
from datetime import datetime

def get_logger(name: str = "bot"):
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"{datetime.now().strftime('%Y%m%d')}.log")
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger
