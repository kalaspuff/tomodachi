import datetime
import pytz
import pytest
from tomodachi.helpers.crontab import get_next_datetime


def test_aliases() -> None:
    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('@yearly', t) == datetime.datetime(2018, 1, 1)
    assert get_next_datetime('@annually', t) == datetime.datetime(2018, 1, 1)
    assert get_next_datetime('@monthly', t) == datetime.datetime(2017, 7, 1)
    assert get_next_datetime('@daily', t) == datetime.datetime(2017, 6, 16)
    assert get_next_datetime('@hourly', t) == datetime.datetime(2017, 6, 15, 11)
    assert get_next_datetime('@minutely', t) == datetime.datetime(2017, 6, 15, 10, 17)


def test_parser() -> None:
    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('* * * * *', t) == datetime.datetime(2017, 6, 15, 10, 17)
    assert get_next_datetime('1 * * * *', t) == datetime.datetime(2017, 6, 15, 11, 1)
    assert get_next_datetime('*/2 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 18)
    assert get_next_datetime('1/2 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 17)
    assert get_next_datetime('1-3/2 * * * *', t) == datetime.datetime(2017, 6, 15, 11, 1)
    assert get_next_datetime('0/4 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 20)
    assert get_next_datetime('7/8 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 23)
    assert get_next_datetime('15 */2 * * *', t) == datetime.datetime(2017, 6, 15, 12, 15)
    assert get_next_datetime('15 */2 * * *', t) == datetime.datetime(2017, 6, 15, 12, 15)
    assert get_next_datetime('15-30 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 17)
    assert get_next_datetime('20-30 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 20)
    assert get_next_datetime('5,10,55 * * * *', t) == datetime.datetime(2017, 6, 15, 10, 55)


def test_isoweekday() -> None:
    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('* * * * 0', t) == datetime.datetime(2017, 6, 18, 0, 0)
    assert get_next_datetime('* * * * 1', t) == datetime.datetime(2017, 6, 19, 0, 0)
    assert get_next_datetime('* * * * 2', t) == datetime.datetime(2017, 6, 20, 0, 0)
    assert get_next_datetime('* * * * 3', t) == datetime.datetime(2017, 6, 21, 0, 0)
    assert get_next_datetime('* * * * 4', t) == datetime.datetime(2017, 6, 15, 10, 17)
    assert get_next_datetime('* * * * 5', t) == datetime.datetime(2017, 6, 16, 0, 0)
    assert get_next_datetime('* * * * 6', t) == datetime.datetime(2017, 6, 17, 0, 0)
    assert get_next_datetime('* * * * 7', t) == datetime.datetime(2017, 6, 18, 0, 0)

    assert get_next_datetime('* * * * mon-tue', t) == datetime.datetime(2017, 6, 19, 0, 0)

    t = datetime.datetime(2017, 6, 19, 10, 16, 50)
    assert get_next_datetime('* * * * 5-6', t) == datetime.datetime(2017, 6, 23, 0, 0)
    assert get_next_datetime('* * * * 0-4', t) == datetime.datetime(2017, 6, 19, 10, 17)
    assert get_next_datetime('* * * * 5-7', t) == datetime.datetime(2017, 6, 23, 0, 0)

    assert get_next_datetime('* * * * fri-sat', t) == datetime.datetime(2017, 6, 23, 0, 0)
    assert get_next_datetime('* * * * sun-fri', t) == datetime.datetime(2017, 6, 19, 10, 17)
    assert get_next_datetime('* * * * fri-sun', t) == datetime.datetime(2017, 6, 23, 0, 0)

    assert get_next_datetime('* * * * 0-7', t) == datetime.datetime(2017, 6, 19, 10, 17)

    with pytest.raises(Exception):
        get_next_datetime('* * * * wed-mon', t)


def test_days_with_isoweekday() -> None:
    t = datetime.datetime(2017, 8, 24, 18, 1, 0)
    assert get_next_datetime('0 10 1-7 * *', t) == datetime.datetime(2017, 9, 1, 10, 0)
    assert get_next_datetime('0 10 * * mon', t) == datetime.datetime(2017, 8, 28, 10, 0)
    assert get_next_datetime('0 10 1-7 * mon', t) == datetime.datetime(2017, 8, 28, 10, 0)
    assert get_next_datetime('0 10 1-25 * mon', t) == datetime.datetime(2017, 8, 25, 10, 0)
    assert get_next_datetime('0 * 1-25 * mon', t) == datetime.datetime(2017, 8, 24, 19, 0)
    assert get_next_datetime('0 * 1-24 * mon', t) == datetime.datetime(2017, 8, 24, 19, 0)
    assert get_next_datetime('0 * 1-23 * mon', t) == datetime.datetime(2017, 8, 28, 0, 0)


def test_timezones() -> None:
    t = datetime.datetime(2017, 6, 15, 10, 16, 50, tzinfo=pytz.UTC)
    assert get_next_datetime('* * * * *', t) == datetime.datetime(2017, 6, 15, 10, 17, tzinfo=pytz.UTC)

    t = pytz.timezone('Europe/Stockholm').localize(datetime.datetime(2017, 6, 15, 10, 16, 50))
    assert get_next_datetime('* * * * *', t) == pytz.timezone('Europe/Stockholm').localize(datetime.datetime(2017, 6, 15, 10, 17))
    assert get_next_datetime('15 */2 * * *', t) == pytz.timezone('Europe/Stockholm').localize(datetime.datetime(2017, 6, 15, 12, 15))


def test_advanced_parsing() -> None:
    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('39 3 L * *', t) == datetime.datetime(2017, 6, 30, 3, 39)
    assert get_next_datetime('10-15,30,45 10 * * *', t) == datetime.datetime(2017, 6, 15, 10, 30)

    t = datetime.datetime(2017, 6, 15, 10, 12, 50)
    assert get_next_datetime('10-15,30,45 10 * * *', t) == datetime.datetime(2017, 6, 15, 10, 13)

    t = datetime.datetime(2017, 6, 15, 9, 12, 50)
    assert get_next_datetime('10-15,30,45 10 * * *', t) == datetime.datetime(2017, 6, 15, 10, 10)

    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('55 7 * * Lsun', t) == datetime.datetime(2017, 6, 25, 7, 55)
    assert get_next_datetime('* * * * Lsun', t) == datetime.datetime(2017, 6, 25)

    assert get_next_datetime('* * * * Lwed-fri', t) == datetime.datetime(2017, 6, 28)
    assert get_next_datetime('* * 4-15 feb-jun wed-fri', t) == datetime.datetime(2017, 6, 15, 10, 17)
    assert get_next_datetime('3-20/2 5 4-15 feb-may *', t) == datetime.datetime(2018, 2, 4, 5, 3)
    assert get_next_datetime('3-20/2 5 4-15 feb-may wed', t) == datetime.datetime(2018, 2, 4, 5, 3)
    assert get_next_datetime('3-20/2 5 10-15 feb-may wed', t) == datetime.datetime(2018, 2, 7, 5, 3)
    assert get_next_datetime('3-20/2 5 * feb-may wed', t) == datetime.datetime(2018, 2, 7, 5, 3)
    assert get_next_datetime('3-20/2 5 4-15 feb-may mon,tue-wed', t) == datetime.datetime(2018, 2, 4, 5, 3)
    assert get_next_datetime('3-20/2 5 4-15 feb-may wed-fri', t) == datetime.datetime(2018, 2, 1, 5, 3)
    assert get_next_datetime('3-20/2 5 7-15 feb-may wed,tue,sat,mon', t) == datetime.datetime(2018, 2, 3, 5, 3)

    assert get_next_datetime('* * 29 2 *', t) == datetime.datetime(2020, 2, 29, 0, 0)
    assert get_next_datetime('* * 29 2 0', t) == datetime.datetime(2018, 2, 4, 0, 0)
    assert get_next_datetime('* * 29 2 0 2020', t) == datetime.datetime(2020, 2, 2, 0, 0)

    assert get_next_datetime('30 5 * jan,mar Ltue', t) == datetime.datetime(2018, 1, 30, 5, 30)

    t = datetime.datetime(2011, 1, 10, 23, 59, 30)
    assert get_next_datetime('0 0 1 jan/2 * 2011-2013', t) == datetime.datetime(2011, 3, 1)

    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('* * 29 2 mon 2048', t) == datetime.datetime(2048, 2, 3, 0, 0)
    assert get_next_datetime('* * 29 2 * 2048', t) == datetime.datetime(2048, 2, 29, 0, 0)
    assert get_next_datetime('* * 29 2 * 2049,2051-2060', t) == datetime.datetime(2052, 2, 29, 0, 0)


def test_impossible_dates() -> None:
    t = datetime.datetime(2017, 6, 15, 10, 16, 50)
    assert get_next_datetime('0 0 1 jan/2 * 2011-2013', t) is None

    with pytest.raises(Exception):
        get_next_datetime('* * 29 2 * 2017-2019', t)

    with pytest.raises(Exception):
        get_next_datetime('* * 29 2 * 2049-2050,2073-2075,2099-2101', t)

    with pytest.raises(Exception):
        get_next_datetime('70 * * *', t)

    with pytest.raises(Exception):
        get_next_datetime('* * 30 2 *', t)

    with pytest.raises(Exception):
        get_next_datetime('* * * * tue-mon', t)

    with pytest.raises(Exception):
        get_next_datetime('* * * x-dec *', t)

    with pytest.raises(Exception):
        get_next_datetime('* * * jan-y *', t)

    with pytest.raises(Exception):
        get_next_datetime('* * * nope *', t)
