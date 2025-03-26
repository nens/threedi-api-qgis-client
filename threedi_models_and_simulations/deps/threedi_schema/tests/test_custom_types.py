import pytest

from threedi_schema.domain.custom_types import clean_csv_string, clean_csv_table


@pytest.mark.parametrize(
    "value",
    [
        "1,2,3",
        "1, 2, 3 ",
        "1,\t2,3",
        "1,\r2,3 ",
        "1,\n2,3 ",
        "1,  2,3",
        "1,  2  ,3",
        " 1,2,3 ",
        "\n1,2,3",
        "\t1,2,3",
        "\r1,2,3",
        "1,2,3\t",
        "1,2,3\n",
        "1,2,3\r",
    ],
)
def test_clean_csv_string(value):
    assert clean_csv_string(value) == "1,2,3"


def test_clean_csv_string_with_whitespace():
    assert clean_csv_string("1,2 3,4") == "1,2 3,4"


@pytest.mark.parametrize(
    "value",
    [
        "1,2,3\n4,5,6",
        "1,2,3\r\n4,5,6",
        "\n1,2,3\n4,5,6",
        "1,2,3\n4,5,6\n",
    ],
)
def test_clean_csv_table(value):
    assert clean_csv_table(value) == "1,2,3\n4,5,6"


@pytest.mark.parametrize(
    "value", [" ", "0 1", "3;5", "foo", "1,2\n3,", ",2", ",2\n3,4"]
)
def test_clean_csv_table_no_fail(value):
    clean_csv_table(value)
