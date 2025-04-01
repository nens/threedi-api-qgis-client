import re

import geoalchemy2
from packaging import version
from sqlalchemy.types import Integer, Text, TypeDecorator, VARCHAR


class Geometry(geoalchemy2.types.Geometry):
    cache_ok = False

    def __init__(self, geometry_type, from_text="ST_GeomFromEWKT"):
        kwargs = {
            "geometry_type": geometry_type,
            "srid": 4326,
            "spatial_index": True,
            "from_text": from_text,
        }
        if version.parse(geoalchemy2.__version__) < version.parse("0.13.0"):
            kwargs["management"] = True
        super().__init__(**kwargs)


class CustomEnum(TypeDecorator):
    """Column type for storing integer python enums.

    The CustomEnum will make use of the backend 'impl' datatype to store
    the data. Data is converted back it's enum_class python object if possible.
    If not, the raw 'impl' is returned.

    CustomEnum should not be used directly but inherited by a class which
    provides the `impl` datatype.
    """

    def __init__(self, enum_class):
        """

        :param enum_class: instance of enum.Enum
        """
        super().__init__()
        self.enum_class = enum_class
        self.enums = [e.value for e in enum_class]

    def process_bind_param(self, value, dialect):
        if isinstance(value, self.enum_class):
            return value.value
        else:
            return value

    def process_result_value(self, value, dialect):
        if value in self.enums:
            return self.enum_class(value)
        else:
            return value


class IntegerEnum(CustomEnum):
    """Column type for storing integer python enums.

    The CustomEnum will make use of the backend 'impl' datatype to store
    the data. Data is converted back it's enum_class python object if possible.
    If not, the raw 'impl' is returned.

    CustomEnum should not be used directly but inherited by a class which
    provides the `impl` datatype.
    """

    cache_ok = True
    impl = Integer


def clean_csv_string(value: str) -> str:
    return re.sub(r"\s*,\s*", ",", value.strip())


class CSVText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = clean_csv_string(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = clean_csv_string(value)
        return value


def clean_csv_table(value: str) -> str:
    # convert windows line endings to unix first
    value = value.replace("\r\n", "\n")
    # remove leading and trailing whitespace
    value = value.strip()
    # clean up each line
    return "\n".join([clean_csv_string(line) for line in value.split("\n")])


class CSVTable(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = clean_csv_table(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = clean_csv_table(value)
        return value


class VarcharEnum(CustomEnum):
    cache_ok = True
    impl = VARCHAR
