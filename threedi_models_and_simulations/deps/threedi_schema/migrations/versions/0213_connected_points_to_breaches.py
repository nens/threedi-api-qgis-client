"""clean unused connected points and transform remaining to potential breaches

Revision ID: 0213
Revises: 0212
Create Date: 2022-12-21 14:54:00

"""
import logging

from alembic import op
from sqlalchemy import Column, Float, ForeignKey, func, Integer, String
from sqlalchemy.orm import declarative_base, Session

from threedi_schema.domain.custom_types import Geometry

# revision identifiers, used by Alembic.
revision = "0213"
down_revision = "0212"
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

## Copy of the ORM at this point in time:

Base = declarative_base()


class Levee(Base):
    __tablename__ = "v2_levee"
    id = Column(Integer, primary_key=True)
    code = Column(String(100))
    crest_level = Column(Float)
    the_geom = Column(
        Geometry(
            "LINESTRING"
        ),
        nullable=False
    )
    material = Column(Integer)
    max_breach_depth = Column(Float)


class CalculationPoint(Base):
    __tablename__ = "v2_calculation_point"
    id = Column(Integer, primary_key=True)

    content_type_id = Column(Integer)
    user_ref = Column(String(80), nullable=False)
    calc_type = Column(Integer)
    the_geom = Column(
        Geometry("POINT"),
        nullable=False
    )


class ConnectedPoint(Base):
    __tablename__ = "v2_connected_pnt"
    id = Column(Integer, primary_key=True)

    calculation_pnt_id = Column(
        Integer, ForeignKey(CalculationPoint.__tablename__ + ".id"), nullable=False
    )
    levee_id = Column(Integer, ForeignKey(Levee.__tablename__ + ".id"))

    exchange_level = Column(Float)
    the_geom = Column(
        Geometry("POINT"),
        nullable=False
    )


class PotentialBreach(Base):
    __tablename__ = "v2_potential_breach"
    id = Column(Integer, primary_key=True)
    code = Column(String(100))
    display_name = Column(String(255))
    exchange_level = Column(Float)
    maximum_breach_depth = Column(Float)
    levee_material = Column(Integer)
    the_geom = Column(
        Geometry("LINESTRING", from_text="ST_GeomFromEWKB"),
        nullable=False
    )
    channel_id = Column(Integer, nullable=False)


class ConnectionNode(Base):
    __tablename__ = "v2_connection_nodes"
    id = Column(Integer, primary_key=True)
    the_geom = Column(
        Geometry("POINT"),
        nullable=False
    )


class Manhole(Base):
    __tablename__ = "v2_manhole"

    id = Column(Integer, primary_key=True)
    connection_node_id = Column(
        Integer,
        ForeignKey(ConnectionNode.__tablename__ + ".id"),
        nullable=False,
        unique=True,
    )


class Channel(Base):
    __tablename__ = "v2_channel"

    id = Column(Integer, primary_key=True)
    calculation_type = Column(Integer, nullable=False)
    dist_calc_points = Column(Float, nullable=True)
    connection_node_start_id = Column(Integer, nullable=False)
    connection_node_end_id = Column(Integer, nullable=False)
    the_geom = Column(
        Geometry(
            "LINESTRING" 
        ),
        nullable=True
    )


def parse_connected_point_user_ref(user_ref: str):
    """Return content_type, content_id, node_number from a user_ref.

    Raises Exception for various parse errors.

    Example
    -------
    >>> parse_connected_point_user_ref("201#123#v2_channels#4)
    ContentType.TYPE_V2_CHANNEL, 123, 3
    """
    _, id_str, type_str, node_nr = user_ref.split("#")
    return type_str, int(id_str), int(node_nr)


def clean_connected_points(session):
    conn_point_ids = [
        x[0]
        for x in session.query(ConnectedPoint.id)
        .join(CalculationPoint, isouter=True)
        .filter(
            (ConnectedPoint.the_geom != CalculationPoint.the_geom)
            | (ConnectedPoint.exchange_level > -9999.0)
            | (ConnectedPoint.levee_id != None)
        )
        .all()
    ]
    session.query(ConnectedPoint).filter(
        ConnectedPoint.id.notin_(conn_point_ids)
    ).delete(synchronize_session="fetch")
    calc_point_ids = [
        x[0]
        for x in session.query(ConnectedPoint.calculation_pnt_id)
        .filter(ConnectedPoint.id.in_(conn_point_ids))
        .all()
    ]
    session.query(CalculationPoint).filter(
        CalculationPoint.id.notin_(calc_point_ids)
    ).delete(synchronize_session="fetch")
    return conn_point_ids


def get_channel_id(session, user_ref):
    """Get channel id and index into channel nodes"""
    type_ref, pk, node_nr = parse_connected_point_user_ref(user_ref)
    if type_ref == "v2_channel":
        return pk, node_nr - 1
    elif type_ref == "v2_manhole":
        return get_channel_id_manhole(session, pk)
    return None, None


def get_channel_id_manhole(session, pk):
    obj = session.query(Manhole).filter(Manhole.id == pk).first()
    if obj is None:
        return None, None
    connection_node_id = obj.connection_node_id

    # find a channel connected to this connection node, with connected calc type
    channels = (
        session.query(Channel)
        .filter(
            (
                (Channel.connection_node_start_id == connection_node_id)
                | (Channel.connection_node_end_id == connection_node_id)
            )
            & Channel.calculation_type.in_([102, 105])
        )
        .all()
    )
    if len(channels) == 0:
        return None, None

    # prefer double connected, and then prefer lowest id
    channel = sorted(channels, key=lambda x: (-x.calculation_type, x.id))[0]
    if channel.connection_node_start_id == connection_node_id:
        node_idx = 0
    else:
        node_idx = -1
    return channel.id, node_idx


def scalar_subquery(query):
    # compatibility between sqlalchemy 1.3 and 1.4
    try:
        return query.scalar_subquery()
    except AttributeError:
        return query.as_scalar()


def get_breach_line_geom(session, conn_point_id, channel_id, node_idx):
    channel = scalar_subquery(
        session.query(Channel.the_geom).filter(Channel.id == channel_id)
    )
    if node_idx == 0:
        breach_line_start = func.ST_PointN(channel, 1)
    elif node_idx == -1:
        breach_line_start = func.ST_PointN(channel, func.ST_NPoints(channel))
    else:
        breach_line_start = func.Snap(CalculationPoint.the_geom, channel, 1e-7)

    return (
        session.query(
            func.AsEWKB(func.MakeLine(breach_line_start, ConnectedPoint.the_geom))
        )
        .join(CalculationPoint)
        .filter(ConnectedPoint.id == conn_point_id)
        .one()[0]
    )


def to_potential_breach(session, conn_point_id):
    connected_point, calculation_point, levee = (
        session.query(
            ConnectedPoint,
            CalculationPoint,
            Levee,
        )
        .join(CalculationPoint)
        .join(Levee, isouter=True)
        .filter(ConnectedPoint.id == conn_point_id)
        .one()
    )

    channel_id, node_idx = get_channel_id(session, calculation_point.user_ref)
    if channel_id is None:
        return

    line_geom = get_breach_line_geom(session, conn_point_id, channel_id, node_idx)

    if connected_point.exchange_level not in (None, -9999.0):
        exchange_level = connected_point.exchange_level
    elif levee is not None:
        exchange_level = levee.crest_level
    else:
        exchange_level = None

    if levee is not None:
        maximum_breach_depth = levee.max_breach_depth
    else:
        maximum_breach_depth = None

    if exchange_level == -9999.0:
        exchange_level = None
    if maximum_breach_depth == -9999.0:
        maximum_breach_depth = None

    return PotentialBreach(
        code="#".join([str(connected_point.id), calculation_point.user_ref])[:100],
        exchange_level=exchange_level,
        maximum_breach_depth=maximum_breach_depth,
        levee_material=levee.material if levee is not None else None,
        the_geom=line_geom,
        channel_id=channel_id,
    )


def upgrade():
    session = Session(bind=op.get_bind())

    conn_point_ids = clean_connected_points(session)
    for conn_point_id in conn_point_ids:
        breach = to_potential_breach(session, conn_point_id)
        if breach is None:
            logger.warning(
                "Connected Point %d will be removed because it "
                "cannot be related to a channel. This may influence the "
                "1D-2D exchange of the model.",
                conn_point_id,
            )
        else:
            session.add(breach)
    session.flush()


def downgrade():
    pass
