import base64
import re

CONTRACT = re.compile(r"\bC[A-Z2-7]{55}\b")
CONTRACT_VERSION = 2 << 3


def crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
            )
    return crc


def is_contract_id(value: str) -> bool:
    try:
        raw = base64.b32decode(value)
    except ValueError:
        return False
    return (
        len(raw) == 35
        and raw[0] == CONTRACT_VERSION
        and int.from_bytes(raw[33:], "little") == crc16(raw[:33])
    )


def find_contract_ids(text: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for match in CONTRACT.finditer(text):
        if is_contract_id(match.group(0)):
            found.append((match.group(0), text.count("\n", 0, match.start()) + 1))
    return found
