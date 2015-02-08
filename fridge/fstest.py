import pytest


def write_file(fs, path, content=u'foo'):
    with fs.open(path, 'w') as f:
        f.write(content)


def assert_file_content_equal(fs, path, content):
    with fs.open(path, 'r') as f:
        assert f.read() == content


def assert_open_raises(fs, path, err, mode='r'):
    with pytest.raises(OSError) as excinfo:
        with fs.open(path, mode):
            pass
    assert excinfo.value.errno == err
    assert excinfo.value.filename == path
