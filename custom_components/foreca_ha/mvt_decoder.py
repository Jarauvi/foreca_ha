"""Module for minimal, dependency-free Mapbox Vector Tile (MVT) decoder."""

from __future__ import annotations

import struct
from typing import Any

# Protobuf wire types.
_WIRE_VARINT = 0
_WIRE_FIXED64 = 1
_WIRE_LENGTH_DELIMITED = 2
_WIRE_FIXED32 = 5

# MVT geometry command ids.
_CMD_MOVE_TO = 1
_CMD_LINE_TO = 2
_CMD_CLOSE_PATH = 7

# Map MVT geometry type numbers to GeoJSON type names.
_GEOMETRY_NAMES = {1: "Point", 2: "LineString", 3: "Polygon"}


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    """Read a base-128 varint from ``buf`` at ``pos``.

    Returns ``(value, new_pos)``.
    """
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("Truncated varint in MVT data")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError("Varint too long in MVT data")


def _zigzag_decode(value: int) -> int:
    """Decode a ZigZag-encoded signed integer."""
    return (value >> 1) ^ -(value & 1)


def _to_signed(value: int) -> int:
    """Convert a raw uint64 into a signed int64 (two's complement)."""
    if value & (1 << 63):
        return value - (1 << 64)
    return value


def _skip_field(buf: bytes, pos: int, wire_type: int) -> int:
    """Skip an unknown field and return the new position."""
    if wire_type == _WIRE_VARINT:
        _, pos = _read_varint(buf, pos)
        return pos
    if wire_type == _WIRE_FIXED64:
        return pos + 8
    if wire_type == _WIRE_LENGTH_DELIMITED:
        length, pos = _read_varint(buf, pos)
        return pos + length
    if wire_type == _WIRE_FIXED32:
        return pos + 4
    raise ValueError(f"Unsupported protobuf wire type: {wire_type}")


def _parse_value(buf: bytes, pos: int, length: int) -> tuple[Any, int]:
    """Parse a single MVT ``Value`` message into a Python value."""
    end = pos + length
    value: Any = None
    while pos < end:
        tag, pos = _read_varint(buf, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07

        if field_num == 1 and wire_type == _WIRE_LENGTH_DELIMITED:  # string_value
            vlen, pos = _read_varint(buf, pos)
            value = buf[pos : pos + vlen].decode("utf-8", errors="replace")
            pos += vlen
        elif field_num == 2 and wire_type == _WIRE_FIXED32:  # float_value
            value = struct.unpack("<f", buf[pos : pos + 4])[0]
            pos += 4
        elif field_num == 3 and wire_type == _WIRE_FIXED64:  # double_value
            value = struct.unpack("<d", buf[pos : pos + 8])[0]
            pos += 8
        elif field_num == 4 and wire_type == _WIRE_VARINT:  # int_value
            raw, pos = _read_varint(buf, pos)
            value = _to_signed(raw)
        elif field_num == 5 and wire_type == _WIRE_VARINT:  # uint_value
            value, pos = _read_varint(buf, pos)
        elif field_num == 6 and wire_type == _WIRE_VARINT:  # sint_value
            raw, pos = _read_varint(buf, pos)
            value = _zigzag_decode(raw)
        elif field_num == 7 and wire_type == _WIRE_VARINT:  # bool_value
            raw, pos = _read_varint(buf, pos)
            value = bool(raw)
        else:
            pos = _skip_field(buf, pos, wire_type)
    return value, end


def _read_packed_uint32(buf: bytes, pos: int, length: int) -> list[int]:
    """Read a packed ``repeated uint32`` field."""
    end = pos + length
    values: list[int] = []
    while pos < end:
        raw, pos = _read_varint(buf, pos)
        values.append(raw)
    return values


def _decode_geometry(
    commands: list[int], geometry_type: int | None
) -> dict[str, Any]:
    """Decode MVT geometry command integers into GeoJSON-like coordinates."""
    parts: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] | None = None
    x = 0
    y = 0
    i = 0
    while i < len(commands):
        command_integer = commands[i]
        i += 1
        cmd_id = command_integer & 0x07
        count = command_integer >> 3

        if cmd_id == _CMD_CLOSE_PATH:
            if current is not None:
                parts.append(current)
                current = None
            continue

        for _ in range(count):
            if i + 1 >= len(commands):
                break
            dx = _zigzag_decode(commands[i])
            dy = _zigzag_decode(commands[i + 1])
            i += 2
            x += dx
            y += dy
            if cmd_id == _CMD_MOVE_TO:
                if current is not None:
                    parts.append(current)
                current = [(x, y)]
            elif cmd_id == _CMD_LINE_TO:
                if current is None:
                    current = []
                current.append((x, y))

    if current is not None:
        parts.append(current)

    gtype = _GEOMETRY_NAMES.get(geometry_type or 1, "Unknown")
    if geometry_type == 1:  # Point / MultiPoint
        coords = [p[0] for p in parts if p]
        coordinates = coords[0] if len(coords) == 1 else coords
    elif geometry_type == 2:  # LineString / MultiLineString
        coordinates = parts[0] if len(parts) == 1 else parts
    else:  # Polygon / unknown
        coordinates = parts

    return {"type": gtype, "coordinates": coordinates}


def _parse_feature(buf: bytes, keys: list[str], values: list[Any]) -> dict[str, Any]:
    """Parse a single MVT ``Feature`` message."""
    feature: dict[str, Any] = {
        "id": None,
        "tags": [],
        "type": None,
        "geometry": [],
    }
    pos = 0
    while pos < len(buf):
        tag, pos = _read_varint(buf, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07

        if field_num == 1 and wire_type == _WIRE_VARINT:  # id
            feature["id"], pos = _read_varint(buf, pos)
        elif field_num == 2 and wire_type == _WIRE_LENGTH_DELIMITED:  # tags (packed)
            length, pos = _read_varint(buf, pos)
            feature["tags"].extend(_read_packed_uint32(buf, pos, length))
            pos += length
        elif field_num == 2 and wire_type == _WIRE_VARINT:  # tags (unpacked)
            raw, pos = _read_varint(buf, pos)
            feature["tags"].append(raw)
        elif field_num == 3 and wire_type == _WIRE_VARINT:  # type
            raw, pos = _read_varint(buf, pos)
            feature["type"] = raw
        elif field_num == 4 and wire_type == _WIRE_LENGTH_DELIMITED:  # geometry (packed)
            length, pos = _read_varint(buf, pos)
            feature["geometry"].extend(_read_packed_uint32(buf, pos, length))
            pos += length
        elif field_num == 4 and wire_type == _WIRE_VARINT:  # geometry (unpacked)
            raw, pos = _read_varint(buf, pos)
            feature["geometry"].append(raw)
        else:
            pos = _skip_field(buf, pos, wire_type)

    # Reconstruct properties from the tag/index pairs.
    properties: dict[str, Any] = {}
    tags = feature["tags"]
    for i in range(0, len(tags) - 1, 2):
        key_idx = tags[i]
        value_idx = tags[i + 1]
        if key_idx < len(keys) and value_idx < len(values):
            properties[keys[key_idx]] = values[value_idx]

    return {
        "id": feature["id"],
        "type": "Feature",
        "properties": properties,
        "geometry": _decode_geometry(feature["geometry"], feature["type"]),
    }


def _parse_layer(buf: bytes) -> dict[str, Any]:
    """Parse a single MVT ``Layer`` message."""
    layer: dict[str, Any] = {
        "name": "",
        "raw_features": [],
        "keys": [],
        "values": [],
        "extent": 4096,
        "version": 2,
    }
    pos = 0
    while pos < len(buf):
        tag, pos = _read_varint(buf, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07

        if field_num == 1 and wire_type == _WIRE_LENGTH_DELIMITED:  # name
            length, pos = _read_varint(buf, pos)
            layer["name"] = buf[pos : pos + length].decode("utf-8", errors="replace")
            pos += length
        elif field_num == 2 and wire_type == _WIRE_LENGTH_DELIMITED:  # features
            length, pos = _read_varint(buf, pos)
            layer["raw_features"].append(buf[pos : pos + length])
            pos += length
        elif field_num == 3 and wire_type == _WIRE_LENGTH_DELIMITED:  # keys
            length, pos = _read_varint(buf, pos)
            layer["keys"].append(
                buf[pos : pos + length].decode("utf-8", errors="replace")
            )
            pos += length
        elif field_num == 4 and wire_type == _WIRE_LENGTH_DELIMITED:  # values
            length, pos = _read_varint(buf, pos)
            value, _ = _parse_value(buf, pos, length)
            layer["values"].append(value)
            pos += length
        elif field_num == 5 and wire_type == _WIRE_VARINT:  # extent
            layer["extent"], pos = _read_varint(buf, pos)
        elif field_num == 15 and wire_type == _WIRE_VARINT:  # version
            layer["version"], pos = _read_varint(buf, pos)
        else:
            pos = _skip_field(buf, pos, wire_type)

    # Features are parsed after keys/values are fully collected, since they
    # reference keys/values by index.
    features = [
        _parse_feature(raw, layer["keys"], layer["values"])
        for raw in layer["raw_features"]
    ]

    return {
        "name": layer["name"],
        "features": features,
        "extent": layer["extent"],
        "version": layer["version"],
    }


def decode(tile_data: bytes) -> dict[str, Any]:
    """Decode a raw MVT tile (``bytes``) into a dict of ``{layer_name: layer}``.

    This is the public entry point, intended as a drop-in replacement for the
    ``mapbox_vector_tile.decode()`` function used by this integration. The
    returned dict is keyed by layer name; each layer dict contains:

    * ``features`` — a list of GeoJSON-like feature dicts with ``properties``,
      ``geometry``, ``type``, and ``id``.
    * ``extent`` — the tile extent (default 4096).
    * ``version`` — the MVT specification version (default 2).

    If the input is empty, ``{}`` is returned.
    """
    if not tile_data:
        return {}

    result: dict[str, Any] = {}
    pos = 0
    while pos < len(tile_data):
        tag, pos = _read_varint(tile_data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07

        if field_num == 3 and wire_type == _WIRE_LENGTH_DELIMITED:  # Tile.layers
            length, pos = _read_varint(tile_data, pos)
            layer_data = tile_data[pos : pos + length]
            layer = _parse_layer(layer_data)
            result[layer["name"]] = layer
            pos += length
        else:
            pos = _skip_field(tile_data, pos, wire_type)

    return result
