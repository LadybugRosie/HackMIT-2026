import secrets
import time
import uuid

# No O/0, I/1/L: class codes are read aloud and typed from a whiteboard.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_id() -> str:
    return str(uuid.uuid4())


def new_class_code(length: int = 6) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def now_ms() -> int:
    return int(time.time() * 1000)
