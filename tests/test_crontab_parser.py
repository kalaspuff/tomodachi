import datetime
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
    assert get_next_datetime('3-20/2 5 4-15 feb-may wed-fri', t) == datetime.datetime(2018, 2, 7, 5, 3)

    t = datetime.datetime(2011, 1, 10, 23, 59, 30)
    assert get_next_datetime('0 0 1 jan/2 * 2011-2013', t) == datetime.datetime(2011, 3, 1)
