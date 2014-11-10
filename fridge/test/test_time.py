from datetime import datetime, timedelta

from fridge.time import (
    datetime2timestamp, START_OF_EPOCH, timestamp2utc, utc2timestamp, utc_time)


def test_utc_time():
    utcnow = lambda: START_OF_EPOCH + timedelta(seconds=22)
    assert utc_time(utcnow=utcnow) == 22


def test_utc2timestamp():
    ts = datetime2timestamp(datetime(1970, 1, 1, second=45))
    assert utc2timestamp(ts) == 45


def test_datetime2timestamp():
    assert datetime2timestamp(START_OF_EPOCH + timedelta(seconds=10)) == 10


def test_timestamp2utc():
    utcfromtimestamp = lambda ts: START_OF_EPOCH + timedelta(seconds=ts + 10)
    assert timestamp2utc(11, utcfromtimestamp=utcfromtimestamp) == 21
