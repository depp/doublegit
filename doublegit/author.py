__all__ = ['parse_author']
import datetime
import collections
import re

Author = collections.namedtuple('Author', 'name email date')

PARSE_OFFSET = re.compile(r'([-+])(\d\d)(\d\d)$')

def parse_timestamp(timestamp):
    timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))
    return timestamp.replace(tzinfo=datetime.timezone.utc)

def parse_offset(offset):
    m = PARSE_OFFSET.match(offset)
    if m is None:
        raise Failurue('Cannot parse offset: {!r}'.format(line[i+1:]))
    offset = datetime.timedelta(
        hours=int(m.group(2)),
        minutes=int(m.group(3)))
    if m.group(1) == '-':
        offset = -offset
    return datetime.timezone(offset)

PARSE_USER = re.compile('([^<]*)(?:<([^>]*)>)$')

def parse_user(user):
    m = PARSE_USER.match(user)
    if m is None:
        raise Failure('Cannot parse user: {!r}'.format(user))
    return m.group(1).rstrip(), m.group(2)

def parse_author(line):
    j = line.rindex(' ')
    i = line.rindex(' ', 0, j)
    name, email = parse_user(line[:i])
    timestamp = parse_timestamp(line[i+1:j])
    offset = parse_offset(line[j+1:])
    timestamp = timestamp.astimezone(offset).isoformat()
    return Author(name, email, timestamp)

if __name__ == '__main__':
    test_in = 'Dietrich Epp <depp@zdome.net> 1368039878 -0700'
    expected_out = Author(
        'Dietrich Epp',
        'depp@zdome.net',
        '2013-05-08T12:04:38-07:00')
    test_out = parse_author(test_in)
    if test_out != expected_out:
        raise Exception('Test failed: expected {!r}, got {!r}'
                        .format(expected_out, test_out))
