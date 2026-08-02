"""Helpers to build minimal MVT tiles for tests.

These helpers encode the Google protobuf wire format directly so that tests
can construct realistic MVT payloads without any third-party dependency.
"""

from __future__ import annotations

import struct
from typing import Iterable


def varint(value: int) -> bytes:
    """Encode a single base-128 varint."""
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            break
    return bytes(result)


def tag(field_num: int, wire_type: int) -> bytes:
    """Encode a protobuf tag (field_number << 3 | wire_type)."""
    return varint((field_num << 3) | wire_type)


def length_delimited(field_num: int, payload: bytes) -> bytes:
    """Encode a length-delimited field."""
    return tag(field_num, 2) + varint(len(payload)) + payload


def value_string(value: str) -> bytes:
    """Encode an MVT ``Value`` message containing a string."""
    return length_delimited(4, length_delimited(1, value.encode("utf-8")))


def value_int(value: int) -> bytes:
    """Encode an MVT ``Value`` message containing an int64."""
    return length_delimited(4, tag(4, 0) + varint(value))


def value_float(value: float) -> bytes:
    """Encode an MVT ``Value`` message containing a float."""
    return length_delimited(4, tag(2, 5) + struct.pack("<f", value))


def feature(
    feature_id: int,
    tags: Iterable[int],
    geometry_type: int,
    geometry_commands: Iterable[int],
) -> bytes:
    """Encode a minimal MVT ``Feature`` message."""
    inner = tag(1, 0) + varint(feature_id)
    packed_tags = b"".join(varint(t) for t in tags)
    inner += tag(2, 2) + varint(len(packed_tags)) + packed_tags
    inner += tag(3, 0) + varint(geometry_type)
    packed_geom = b"".join(varint(c) for c in geometry_commands)
    inner += tag(4, 2) + varint(len(packed_geom)) + packed_geom
    return length_delimited(2, inner)


def layer(
    name: str,
    features: Iterable[bytes],
    keys: Iterable[str],
    values: Iterable[bytes],
    extent: int = 4096,
    version: int = 2,
) -> bytes:
    """Encode a minimal MVT ``Layer`` message."""
    inner = length_delimited(1, name.encode("utf-8"))
    for f in features:
        inner += f
    for k in keys:
        inner += length_delimited(3, k.encode("utf-8"))
    for v in values:
        inner += v
    inner += tag(5, 0) + varint(extent)
    inner += tag(15, 0) + varint(version)
    return length_delimited(3, inner)


def build_tile(layers: Iterable[bytes]) -> bytes:
    """Build a complete ``Tile`` message with one or more layers."""
    return b"".join(layers)


def snow_depth_tile(observations: Iterable[tuple[str, int, str]]) -> bytes:
    """Build a Foreca-style snow-depth observation tile.

    ``observations`` is an iterable of ``(station_name, depth_cm, time_str)``
    tuples. The resulting tile has a layer named ``"data"`` whose features
    carry ``name``, ``val`` and ``time`` properties (matching what the
    integration's coordinator expects).
    """
    keys = ["name", "val", "time"]
    values: list[bytes] = []
    features: list[bytes] = []
    for idx, (name, val, time) in enumerate(observations):
        base = idx * 3
        values.extend(
            [
                value_string(name),
                value_int(val),
                value_string(time),
            ]
        )
        features.append(
            feature(
                feature_id=idx + 1,
                tags=[0, base, 1, base + 1, 2, base + 2],
                geometry_type=1,  # Point
                geometry_commands=[9, 0, 0],  # MoveTo(1): (0,0)
            )
        )
    return build_tile([layer("data", features, keys, values)])

