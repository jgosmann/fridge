from fridge.cli import FridgeCli
from fridge.api import Fridge
from hamcrest import assert_that, contains, has_item, instance_of, is_
from matchers import class_with
from unittest.mock import MagicMock
import os
import shutil
import tempfile


class TestCli(object):
    def setUp(self):
        self.fridge_path = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.fridge_path)
        self.cli = FridgeCli()
        self.cli.environ = {'EDITOR': 'editor'}
        self.cli.call = MagicMock()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.fridge_path)

    def test_init_creates_new_fridge(self):
        self.cli.main(['init'])
        # check correct initialization by trying to open the fridge
        Fridge(self.fridge_path)

    def test_allows_to_create_new_experiments(self):
        expname = 'newone'
        desc = 'desc'

        def mock_editor(args):
            with open(args[1], 'w') as file:
                file.write(desc)
            return 0

        self.cli.call.side_effect = mock_editor
        self.cli.main(['init'])
        self.cli.main(['experiment', expname])
        fridge = Fridge(self.fridge_path)
        assert_that(len(self.cli.call.call_args_list), is_(1))
        assert_that(
            self.cli.call.call_args_list[0][0][0],
            contains('editor', instance_of(str)))
        assert_that(fridge.experiments, has_item(class_with(
            name=expname, description=desc)))

    # TODO empty editor
    # TODO use argument instead of editor
    # TODO test reinit/FridgeError
    # TODO test init args
    # TODO unknown subcommand
