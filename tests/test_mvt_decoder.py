"""Tests for the bundled MVT decoder (mvt_decoder.py).

A minimal valid MVT tile is programmatically constructed  using the protobuf wire
format, decoded with a custom module, the output is verified that it matches the expected
shape (layer name, feature properties, geometry, extent, version).

The decoder module is loaded directly (bypassing the package ``__init__.py``)
so these tests do not require the Home Assistant runtime or its dependencies.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

_PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "foreca_ha"
_SPEC = importlib.util.spec_from_file_location(
    "foreca_ha_mvt_decoder", _PKG_DIR / "mvt_decoder.py"
)
assert _SPEC and _SPEC.loader
mvt_decoder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mvt_decoder)


# ---------------------------------------------------------------------------
# Helper: wire-format builders
# ---------------------------------------------------------------------------

def _varint(value: int) -> bytes:
    """Encode a single varint."""
    result: list[int] = []
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not (value and byte & 0x80):
            break
    return bytes(result)


def _tag(field_num: int, wire_type: int) -> bytes:
    """Encode a protobuf tag (field_number << 3 | wire_type)."""
    return _varint((field_num << 3) | wire_type)


def _length_delimited(field_num: int, payload: bytes) -> bytes:
    """Encode a length-delimited field."""
    return _tag(field_num, 2) + _varint(len(payload)) + payload


def _value_string(s: str) -> bytes:
    """Encode an MVT ``Value`` message containing a string."""
    inner = _length_delimited(1, s.encode("utf-8"))
    return _length_delimited(4, inner)


def _value_int(v: int) -> bytes:
    """Encode an MVT ``Value`` message containing an int64."""
    inner = _tag(4, 0) + _varint(v)
    return _length_delimited(4, inner)


def _value_float(v: float) -> bytes:
    """Encode an MVT ``Value`` message containing a float."""
    inner = _tag(2, 5) + struct.pack("<f", v)
    return _length_delimited(4, inner)


def _feature(
    feature_id: int,
    tags: list[int],
    geometry_type: int,
    geometry_commands: list[int],
) -> bytes:
    """Encode a minimal MVT ``Feature`` message."""
    inner = b""
    # id (field 1, varint)
    inner += _tag(1, 0) + _varint(feature_id)
    # tags (field 2, packed)
    packed_tags = b"".join(_varint(t) for t in tags)
    inner += _tag(2, 2) + _varint(len(packed_tags)) + packed_tags
    # type (field 3, varint)
    inner += _tag(3, 0) + _varint(geometry_type)
    # geometry (field 4, packed)
    packed_geom = b"".join(_varint(c) for c in geometry_commands)
    inner += _tag(4, 2) + _varint(len(packed_geom)) + packed_geom
    return _length_delimited(2, inner)


def _layer(
    name: str,
    features: list[bytes],
    keys: list[str],
    values: list[bytes],
    extent: int = 4096,
    version: int = 2,
) -> bytes:
    """Encode a minimal MVT ``Layer`` message."""
    inner = b""
    # name (field 1)
    inner += _length_delimited(1, name.encode("utf-8"))
    # features (field 2, repeated)
    for f in features:
        inner += f
    # keys (field 3, repeated)
    for k in keys:
        inner += _length_delimited(3, k.encode("utf-8"))
    # values (field 4, repeated)
    for v in values:
        inner += v
    # extent (field 5, varint)
    inner += _tag(5, 0) + _varint(extent)
    # version (field 15, varint)
    inner += _tag(15, 0) + _varint(version)
    return _length_delimited(3, inner)


def _build_tile(layers: list[bytes]) -> bytes:
    """Build a complete ``Tile`` message with one or more layers."""
    result = b""
    for layer_data in layers:
        result += layer_data
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMvtDecoder:
    """Test suite for the custom MVT decoder."""

    def test_decode_empty(self) -> None:
        """Empty input returns empty dict."""
        assert mvt_decoder.decode(b"") == {}

    def test_decode_single_layer_single_feature(self) -> None:
        """Decode a tile with one layer containing one feature with properties."""
        lay = _layer(
            name="data",
            features=[
                _feature(
                    feature_id=1,
                    tags=[0, 0, 1, 1],  # key0=name, val0="foo"; key1=val, val1=42
                    geometry_type=1,  # Point
                    geometry_commands=[9, 0, 0],  # MoveTo(1): (0,0)
                ),
            ],
            keys=["name", "val"],
            values=[_value_string("foo"), _value_int(42)],
            extent=4096,
            version=2,
        )
        tile = _build_tile([lay])
        result = mvt_decoder.decode(tile)
        assert "data" in result, f"Expected layer 'data', got {list(result.keys())}"
        layer = result["data"]
        assert layer["extent"] == 4096
        assert layer["version"] == 2
        assert len(layer["features"]) == 1
        feat = layer["features"][0]
        assert feat["type"] == "Feature"
        assert feat["properties"]["name"] == "foo"
        assert feat["properties"]["val"] == 42
        assert feat["geometry"]["type"] == "Point"

    def test_decode_two_layers(self) -> None:
        """Decode a tile with two layers."""
        lay1 = _layer(
            name="snow",
            features=[
                _feature(
                    feature_id=10,
                    tags=[0, 0, 1, 1],
                    geometry_type=1,
                    geometry_commands=[9, 0, 0],
                ),
            ],
            keys=["name", "val"],
            values=[_value_string("station_a"), _value_int(15)],
            extent=4096,
            version=2,
        )
        lay2 = _layer(
            name="temp",
            features=[
                _feature(
                    feature_id=20,
                    tags=[0, 0],
                    geometry_type=1,
                    geometry_commands=[9, 0, 0],
                ),
            ],
            keys=["name"],
            values=[_value_string("station_b")],
            extent=2048,
            version=2,
        )
        tile = _build_tile([lay1, lay2])
        result = mvt_decoder.decode(tile)
        assert "snow" in result
        assert "temp" in result
        assert len(result["snow"]["features"]) == 1
        assert len(result["temp"]["features"]) == 1
        assert result["temp"]["extent"] == 2048

    def test_decode_realistic_snow_obs(self) -> None:
        """Simulate a snow-depth observation tile structure.

        The Foreca snow-depth tile uses a layer named 'data' with features
        that have properties: name (str), val (int), time (str).
        """
        features = [
            _feature(
                feature_id=1,
                tags=[0, 0, 1, 1, 2, 2],
                geometry_type=1,
                geometry_commands=[9, 0, 0],  # MoveTo(1): (0,0)
            ),
            _feature(
                feature_id=2,
                tags=[0, 0, 1, 1, 2, 2],
                geometry_type=1,
                geometry_commands=[9, 0, 0],
            ),
        ]
        lay = _layer(
            name="data",
            features=features,
            keys=["name", "val", "time"],
            values=[
                _value_string("Mikkeli lentoasema"),
                _value_int(12),
                _value_string("20250328060000"),
            ],
            extent=4096,
            version=2,
        )
        tile = _build_tile([lay])
        result = mvt_decoder.decode(tile)
        assert "data" in result
        layer = result["data"]
        assert len(layer["features"]) == 2
        for feat in layer["features"]:
            assert feat["properties"]["name"] == "Mikkeli lentoasema"
            assert feat["properties"]["val"] == 12
            assert feat["properties"]["time"] == "20250328060000"

    def test_decode_float_value(self) -> None:
        """Ensure float values are decoded correctly."""
        lay = _layer(
            name="data",
            features=[
                _feature(
                    feature_id=1,
                    tags=[0, 0],
                    geometry_type=1,
                    geometry_commands=[9, 0, 0],
                ),
            ],
            keys=["val"],
            values=[_value_float(3.5)],
            extent=4096,
            version=2,
        )
        tile = _build_tile([lay])
        result = mvt_decoder.decode(tile)
        feat = result["data"]["features"][0]
        assert feat["properties"]["val"] == pytest.approx(3.5, abs=1e-6)

    def test_decode_no_features(self) -> None:
        """A layer with zero features decodes to an empty list."""
        lay = _layer(
            name="empty",
            features=[],
            keys=[],
            values=[],
            extent=4096,
            version=2,
        )
        tile = _build_tile([lay])
        result = mvt_decoder.decode(tile)
        assert result["empty"]["features"] == []

    def test_decode_unknown_fields_skipped(self) -> None:
        """Unknown fields in a layer should be silently skipped."""
        # We add a fake field (field_num=99) with a junk value to ensure
        # the parser doesn't crash.
        fake_field = _tag(99, 2) + _varint(4) + b"junk"
        inner = (
            _length_delimited(1, b"data")
            + fake_field
            + _length_delimited(3, b"name")
            + _value_string("test")
            + _tag(5, 0) + _varint(4096)
            + _tag(15, 0) + _varint(2)
        )
        lay = _length_delimited(3, inner)
        tile = _build_tile([lay])
        result = mvt_decoder.decode(tile)
        assert "data" in result
        # No features, but shouldn't crash.
        assert result["data"]["features"] == []

    # ------------------------------------------------------------------
    # Geometry decoding edge cases
    # ------------------------------------------------------------------

    def test_decode_line_string(self) -> None:
        """A LineString feature is decoded with its coordinates."""
        # MoveTo(1): (1,1); LineTo(2): (2,3), (4,1).
        # Deltas: +1,+1 -> zigzag 2,2 ; +1,+2 -> 2,4 ; +2,-2 -> 4,3
        commands = [9, 2, 2, 18, 2, 4, 4, 3]
        lay = _layer(
            name="data",
            features=[
                _feature(1, [0, 0], geometry_type=2, geometry_commands=commands),
            ],
            keys=["name"],
            values=[_value_string("path")],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["geometry"]["type"] == "LineString"
        assert feat["geometry"]["coordinates"] == [(1, 1), (2, 3), (4, 1)]

    def test_decode_polygon_with_close(self) -> None:
        """A Polygon with a ClosePath command is decoded."""
        # MoveTo(1): (0,0); LineTo(2): (3,2), (1,4); ClosePath.
        # Deltas: +0,+0 -> 0,0 ; +3,+2 -> 6,4 ; -2,+2 -> 3,4
        commands = [9, 0, 0, 18, 6, 4, 3, 4, 15]
        lay = _layer(
            name="data",
            features=[
                _feature(1, [0, 0], geometry_type=3, geometry_commands=commands),
            ],
            keys=["name"],
            values=[_value_string("poly")],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["geometry"]["type"] == "Polygon"
        # A single ring polygon is represented as one list of coordinate pairs.
        coords = feat["geometry"]["coordinates"]
        assert len(coords) == 1
        assert coords[0] == [(0, 0), (3, 2), (1, 4)]



    def test_decode_multipoint(self) -> None:
        """Multiple MoveTo commands produce a MultiPoint."""
        commands = [9, 0, 0, 9, 2, 4]  # MoveTo(0,0), MoveTo(1,2)
        lay = _layer(
            name="data",
            features=[
                _feature(1, [], geometry_type=1, geometry_commands=commands),
            ],
            keys=[],
            values=[],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["geometry"]["type"] == "Point"
        assert feat["geometry"]["coordinates"] == [(0, 0), (1, 2)]

    # ------------------------------------------------------------------
    # Value type decoding edge cases
    # ------------------------------------------------------------------

    def test_decode_double_value(self) -> None:
        """A double-typed Value decodes correctly."""
        inner = _tag(3, 1) + struct.pack("<d", 2.75)  # field 3 = double_value
        val = _length_delimited(4, inner)
        lay = _layer(
            name="data",
            features=[_feature(1, [0, 0], 1, [9, 0, 0])],
            keys=["val"],
            values=[val],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["properties"]["val"] == pytest.approx(2.75, abs=1e-9)

    def test_decode_uint_value(self) -> None:
        """A uint-typed Value decodes correctly."""
        inner = _tag(5, 0) + _varint(300)  # field 5 = uint_value
        val = _length_delimited(4, inner)
        lay = _layer(
            name="data",
            features=[_feature(1, [0, 0], 1, [9, 0, 0])],
            keys=["val"],
            values=[val],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["properties"]["val"] == 300

    def test_decode_sint_value(self) -> None:
        """A sint-typed (ZigZag) Value decodes correctly."""
        inner = _tag(6, 0) + _varint(7)  # field 6 = sint_value (zigzag of 3)
        val = _length_delimited(4, inner)
        lay = _layer(
            name="data",
            features=[_feature(1, [0, 0], 1, [9, 0, 0])],
            keys=["val"],
            values=[val],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["properties"]["val"] == -4

    def test_decode_bool_value(self) -> None:
        """A bool-typed Value decodes correctly."""
        inner = _tag(7, 0) + _varint(1)  # field 7 = bool_value
        val = _length_delimited(4, inner)
        lay = _layer(
            name="data",
            features=[_feature(1, [0, 0], 1, [9, 0, 0])],
            keys=["flag"],
            values=[val],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["properties"]["flag"] is True

    # ------------------------------------------------------------------
    # Field-encoding edge cases
    # ------------------------------------------------------------------

    def test_decode_unpacked_tags_and_geometry(self) -> None:
        """Unpacked (non-packed) tags/geometry fields are handled."""
        inner = b""
        inner += _tag(1, 0) + _varint(1)  # id
        # Unpacked tags: field 2 as individual varints.
        for t in (0, 0, 1, 1):
            inner += _tag(2, 0) + _varint(t)
        inner += _tag(3, 0) + _varint(1)  # type
        # Unpacked geometry: field 4 as individual varints.
        for c in (9, 0, 0):
            inner += _tag(4, 0) + _varint(c)
        feature_msg = _length_delimited(2, inner)

        lay = _layer(
            name="data",
            features=[feature_msg],
            keys=["name", "val"],
            values=[_value_string("foo"), _value_int(42)],
        )
        tile = _build_tile([lay])
        feat = mvt_decoder.decode(tile)["data"]["features"][0]
        assert feat["properties"]["name"] == "foo"
        assert feat["properties"]["val"] == 42
        assert feat["geometry"]["type"] == "Point"

    def test_decode_truncated_data_raises(self) -> None:
        """Truncated varint data raises ValueError."""
        with pytest.raises(ValueError):
            mvt_decoder.decode(b"\x80")

    def test_decode_bad_value_bytes(self) -> None:
        """Garbage bytes for a value field do not crash with an uncaught error."""
        # A value with a truncated float field.
        val = _length_delimited(4, _tag(2, 5) + b"\x01")  # only 1 byte of float
        lay = _layer(
            name="data",
            features=[_feature(1, [0, 0], 1, [9, 0, 0])],
            keys=["val"],
            values=[val],
        )
        tile = _build_tile([lay])
        # Should either raise ValueError or return something; we just ensure
        # the module's decode can attempt it without an OOB on the buffer.
        try:
            mvt_decoder.decode(tile)
        except ValueError:
            pass



