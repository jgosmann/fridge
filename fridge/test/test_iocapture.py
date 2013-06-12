from fridge.iocapture import CaptureStdout, CaptureStderr
from hamcrest import assert_that, equal_to, is_
from io import StringIO
from unittest.mock import patch, MagicMock
import sys


class TestCaptureStdout(object):
    def test_captures_stdout(self):
        capture = StringIO()
        with patch('sys.stdout'):
            with CaptureStdout(capture):
                print('Text')
        assert_that(capture.getvalue(), is_(equal_to('Text\n')))

    def test_stdout_output_is_not_supressed(self):
        buffer = StringIO()
        with patch('sys.stdout') as stdout_mock:
            with CaptureStdout(MagicMock()):
                stdout_mock.write.side_effect = buffer.write
                print('Text')
        assert_that(buffer.getvalue(), is_(equal_to('Text\n')))


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
