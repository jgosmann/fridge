from fridge.iocapture import CaptureStdout, CaptureStderr
from hamcrest import assert_that, equal_to, is_
try:
    from unittest.mock import patch, MagicMock
except:
    from mock import patch, MagicMock
import os
import sys

if sys.version_info[0] < 3:
    from io import BytesIO as StringIO
else:
    from io import StringIO


class TestCaptureStdout(object):
    def test_captures_stdout(self):
        capture = StringIO()
        with patch('sys.stdout'):
            with CaptureStdout(capture):
                print('Text')
        assert_that(capture.getvalue(), is_(equal_to('Text' + os.linesep)))

    def test_stdout_output_is_not_supressed(self):
        buffer = StringIO()
        with patch('sys.stdout') as stdout_mock:
            stdout_mock.write = MagicMock()
            with CaptureStdout(MagicMock()):
                stdout_mock.write.side_effect = buffer.write
                print('Text')
        assert_that(buffer.getvalue(), is_(equal_to('Text' + os.linesep)))


class TestCaptureStderr(object):
    def test_captures_stdout(self):
        capture = StringIO()
        with patch('sys.stderr'):
            with CaptureStderr(capture):
                sys.stderr.write('Text\n')
        assert_that(capture.getvalue(), is_(equal_to('Text\n')))

    def test_stderr_output_is_not_supressed(self):
        buffer = StringIO()
        with patch('sys.stderr') as stderr_mock:
            with CaptureStderr(MagicMock()):
                stderr_mock.write.side_effect = buffer.write
                sys.stderr.write('Text\n')
        assert_that(buffer.getvalue(), is_(equal_to('Text\n')))
