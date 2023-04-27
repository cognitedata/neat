import hashlib
import uuid
from datetime import datetime
from pathlib import Path


def get_iso8601_timestamp_now_unaware():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def get_file_hash(file_path: Path) -> str:
    if isinstance(file_path, str):
        file_path = Path(file_path)
    return hashlib.md5(file_path.read_bytes()).hexdigest()


def generate_run_id() -> str:
    # Generate a random run guid
    return str(uuid.uuid4())
