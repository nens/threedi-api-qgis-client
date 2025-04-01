import struct

import pytest

from threedi_schema import ModelSchema, ThreediDatabase

# from threedi_schema.migrations.versions import 0213_connected_points_to_breaches
module_name = "0213_connected_points_to_breaches"
migration_213 = getattr(
    __import__("threedi_schema.migrations.versions", fromlist=[module_name]),
    module_name,
)

CalculationPoint = migration_213.CalculationPoint
ConnectedPoint = migration_213.ConnectedPoint
Levee = migration_213.Levee
PotentialBreach = migration_213.PotentialBreach
ConnectionNode = migration_213.ConnectionNode
Manhole = migration_213.Manhole
Channel = migration_213.Channel


@pytest.fixture
def sqlite_v212():
    """An in-memory database with schema version 212"""
    db = ThreediDatabase("")
    ModelSchema(db).upgrade("0212", backup=False)
    return db


@pytest.fixture
def session(sqlite_v212):
    return sqlite_v212.get_session()


def parse_hexewkb(ewkb):
    """Extract 4 line coordinates from an ewkb"""
    return struct.unpack("4d", bytes.fromhex(ewkb)[-32:])


GEOM1 = "SRID=4326;POINT (0 0)"
GEOM2 = "SRID=4326;POINT (0 1)"
CHANNEL = "SRID=4326;LINESTRING(0 0,10 0)"
CHANNEL_INV = "SRID=4326;LINESTRING(10 0,0 0)"
LINE = "0102000020E610000002000000000000000000000000000000000000000000000000000000000000000000F03F"


@pytest.mark.parametrize(
    "objs",
    [
        [CalculationPoint(id=1, the_geom=GEOM1)],
        [ConnectedPoint(id=1, the_geom=GEOM1, calculation_pnt_id=None)],
        [ConnectedPoint(id=1, the_geom=GEOM1, calculation_pnt_id=1)],
        [
            CalculationPoint(id=1, the_geom=GEOM1),
            ConnectedPoint(id=1, the_geom=GEOM1, calculation_pnt_id=1),
        ],
        [
            CalculationPoint(id=1, the_geom=GEOM1),
            ConnectedPoint(id=1, the_geom=GEOM1, calculation_pnt_id=1),
            ConnectedPoint(id=2, the_geom=GEOM1, calculation_pnt_id=1),
        ],
    ],
)
def test_clean_connected_points(session, objs):
    session.add_all(objs)
    session.flush()
    migration_213.clean_connected_points(session)
    assert session.query(CalculationPoint).count() == 0
    assert session.query(ConnectedPoint).count() == 0


@pytest.mark.parametrize(
    "objs",
    [
        [
            CalculationPoint(id=1, the_geom=GEOM1),
            ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
        ],
        [
            CalculationPoint(id=1, the_geom=GEOM1),
            ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
            ConnectedPoint(id=2, the_geom=GEOM2, calculation_pnt_id=1),
        ],
        [
            CalculationPoint(id=1, the_geom=GEOM1),
            ConnectedPoint(
                id=1, the_geom=GEOM2, calculation_pnt_id=1, exchange_level=1.0
            ),
        ],
        [
            CalculationPoint(id=1, the_geom=GEOM1),
            ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1, levee_id=1),
        ],
    ],
)
def test_clean_connected_points_keep(session, objs):
    session.add_all(objs)
    session.flush()
    migration_213.clean_connected_points(session)

    actual = (
        session.query(CalculationPoint).count() + session.query(ConnectedPoint).count()
    )
    assert actual == len(objs)


def todict(x):
    return {col.name: getattr(x, col.name) for col in x.__table__.columns}


def assert_sqlalchemy_objects_equal(a, b):
    assert a.__class__ is b.__class__
    if a is None:
        return
    assert todict(a) == todict(b)


@pytest.mark.parametrize(
    "objs,expected",
    [
        [
            [
                CalculationPoint(id=1, user_ref="123#4#v2_channel#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Channel(id=4, the_geom=CHANNEL),
            ],
            PotentialBreach(channel_id=4, the_geom=LINE, code="1#123#4#v2_channel#1"),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#4#v2_channel#1"),
                ConnectedPoint(
                    id=1, the_geom=GEOM2, calculation_pnt_id=1, exchange_level=1.1
                ),
                Channel(id=4, the_geom=CHANNEL),
            ],
            PotentialBreach(
                channel_id=4,
                the_geom=LINE,
                exchange_level=1.1,
                code="1#123#4#v2_channel#1",
            ),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#4#v2_channel#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1, levee_id=4),
                Levee(id=4, crest_level=1.1),
                Channel(id=4, the_geom=CHANNEL),
            ],
            PotentialBreach(
                channel_id=4,
                the_geom=LINE,
                exchange_level=1.1,
                code="1#123#4#v2_channel#1",
            ),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#4#v2_channel#1"),
                ConnectedPoint(
                    id=1,
                    the_geom=GEOM2,
                    calculation_pnt_id=1,
                    exchange_level=1.1,
                    levee_id=4,
                ),
                Levee(id=4, crest_level=1.2, max_breach_depth=0.5, material=1),
                Channel(id=4, the_geom=CHANNEL),
            ],
            PotentialBreach(
                channel_id=4,
                the_geom=LINE,
                exchange_level=1.1,
                maximum_breach_depth=0.5,
                levee_material=1,
                code="1#123#4#v2_channel#1",
            ),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#3#v2_manhole#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Manhole(id=3, connection_node_id=6),
                ConnectionNode(id=6),
                Channel(
                    id=4,
                    the_geom=CHANNEL,
                    connection_node_start_id=6,
                    calculation_type=102,
                ),
            ],
            PotentialBreach(channel_id=4, the_geom=LINE, code="1#123#3#v2_manhole#1"),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#3#v2_manhole#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Manhole(id=3, connection_node_id=6),
                ConnectionNode(id=6),
                Channel(
                    id=4,
                    the_geom=CHANNEL_INV,
                    connection_node_end_id=6,
                    calculation_type=102,
                ),
            ],
            PotentialBreach(channel_id=4, the_geom=LINE, code="1#123#3#v2_manhole#1"),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#3#v2_manhole#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Manhole(id=3, connection_node_id=6),
                ConnectionNode(id=6),
                Channel(
                    id=4,
                    the_geom=CHANNEL,
                    connection_node_start_id=6,
                    calculation_type=105,
                ),
            ],
            PotentialBreach(channel_id=4, the_geom=LINE, code="1#123#3#v2_manhole#1"),
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#3#v2_manhole#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Manhole(id=3, connection_node_id=6),
                ConnectionNode(id=6),
            ],
            None,
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#3#v2_manhole#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Manhole(id=3, connection_node_id=6),
                ConnectionNode(id=6),
                Channel(id=4, connection_node_start_id=6, calculation_type=101),
            ],
            None,
        ],
        [
            [
                CalculationPoint(id=1, user_ref="123#3#v2_manhole#1"),
                ConnectedPoint(id=1, the_geom=GEOM2, calculation_pnt_id=1),
                Manhole(id=3, connection_node_id=6),
                ConnectionNode(id=6),
                Channel(id=3, connection_node_start_id=6, calculation_type=102),
                Channel(id=5, connection_node_start_id=6, calculation_type=105),
                Channel(
                    id=4,
                    the_geom=CHANNEL_INV,
                    connection_node_end_id=6,
                    calculation_type=105,
                ),
            ],
            PotentialBreach(channel_id=4, the_geom=LINE, code="1#123#3#v2_manhole#1"),
        ],
    ],
)
def test_to_potential_breach(session, objs, expected):
    session.add_all(objs)
    session.flush()
    actual = migration_213.to_potential_breach(session, 1)

    assert_sqlalchemy_objects_equal(actual, expected)


@pytest.mark.parametrize(
    "node_idx,calc_pnt_x,calc_pnt_y,x,y",
    [
        (0, 0, 0, 0, 0),
        (-1, 0, 0, 10, 10),
        (1, 0, 5, 0, 5),
        (1, 0, 10, 0, 10),
        (1, 0, 10 + 1e-8, 0, 10),
        (2, 10 + 7e-8, 10 - 7e-8, 10, 10),
    ],
)
def test_get_breach_line_geom(session, node_idx, calc_pnt_x, calc_pnt_y, x, y):
    objs = [
        ConnectedPoint(id=1, the_geom="SRID=4326;POINT (10 0)", calculation_pnt_id=2),
        CalculationPoint(id=2, the_geom=f"SRID=4326;POINT({calc_pnt_x} {calc_pnt_y})"),
        Channel(id=3, the_geom="SRID=4326;LINESTRING(0 0,0 10,10 10)"),
    ]

    session.add_all(objs)
    session.flush()
    geom = migration_213.get_breach_line_geom(session, 1, 3, node_idx)
    x1, y1, x2, y2 = parse_hexewkb(geom)
    assert x1 == x
    assert y1 == y
    assert x2 == 10.0
    assert y2 == 0.0
