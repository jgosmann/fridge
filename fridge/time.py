from datetime import datetime

START_OF_EPOCH = datetime(1970, 1, 1)


def utc_time(utcnow=datetime.utcnow):
    return datetime2timestamp(utcnow())


def timestamp2utc(timestamp, utcfromtimestamp=datetime.utcfromtimestamp):
    return datetime2timestamp(utcfromtimestamp(timestamp))


def datetime2timestamp(dt):
    return (dt - START_OF_EPOCH).total_seconds()


def utc2timestamp(utc, utcfromtimestamp=datetime.utcfromtimestamp):
    diff = START_OF_EPOCH - utcfromtimestamp(0.)
    return utc - diff.total_seconds()
