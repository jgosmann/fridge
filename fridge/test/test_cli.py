from fridge.cli import FridgeCli
from fridge.api import Fridge
import os
import shutil
import tempfile


class TestCli(object):
    def setUp(self):
        self.fridge_path = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.fridge_path)
        self.cli = FridgeCli()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.fridge_path)

    def test_init_creates_new_fridge(self):
        self.cli.main('init')
        # check correct initialization by trying to open the fridge
        Fridge(self.fridge_path)

    # TODO test reinit/FridgeError
    # TODO unknown subcommand
