from .domain import constants, models  # noqa

"""
Put features in beta development in these lists to prevent users from using them, in the SQLAlchemy format used in the schema.
"""

BETA_COLUMNS = []
"""This list contains beta columns, e.g. models.SomeTable.some_column"""

BETA_VALUES = []
"""
This list contains dicts with lists of beta values for columns, where the dict has the format:
{
    "columns": [
        models.SomeTable.some_column,
        models.SomeTable.some_other_column,
    ],
    "values": [
        constants.SomeConstantsClass.SOMEENUMVALUE,
        "or just some random string",
    ]
}
The modelchecker will go through each column and give an error when a beta value is used for its associated column.
"""
