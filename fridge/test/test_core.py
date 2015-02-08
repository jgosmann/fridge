import os.path
import stat

from mock import MagicMock
import pytest

from fridge.core import (
    AmbiguousReferenceError, Branch, BranchExistsError, Commit, DataObject,
    Fridge, FridgeCore, Reference, SnapshotItem, UnknownReferenceError, Stat)
from fridge.fstest import write_file
from fridge.memoryfs import MemoryFS


def create_file_status():
    return Stat(
        st_mode=(
            stat.S_IFREG |
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP |
            stat.S_IROTH | stat.S_IWOTH),
        st_size=123, st_atime=4.56, st_mtime=7.89)


@pytest.fixture
def fs():
    return MemoryFS()


@pytest.fixture
def fridge_core(fs):
    return FridgeCore.init(os.curdir, fs)


@pytest.fixture
def fridge(fridge_core, fs):
    return Fridge(fridge_core, fs)


class TestDataObject(object):
    # pylint: disable=no-member

    class A(DataObject):
        __slots__ = ['a', 'b']

    class LikeA(DataObject):
        __slots__ = ['a', 'b']

    class B(DataObject):
        __slots__ = 'b'

    def test_raises_on_too_many_args(self):
        with pytest.raises(TypeError):
            self.A(1, 2, 3)

    def test_raises_on_too_few_args(self):
        with pytest.raises(TypeError):
            self.A(1)

    def test_accepts_positional_args(self):
        a = self.A(1, 2)
        assert a.a == 1 and a.b == 2

    def test_raises_on_wrong_keyword_arg(self):
        with pytest.raises(TypeError):
            self.A(1, 2, z=3)
        with pytest.raises(TypeError):
            self.A(1, z=3)

    def test_raises_on_duplicate_arg(self):
        with pytest.raises(TypeError):
            self.A(1, 2, a=1)
        with pytest.raises(TypeError):
            self.A(1, a=1)

    def test_accepts_keyword_args(self):
        a = self.A(b=1, a=2)
        assert a.b == 1 and a.a == 2

    def test_accepts_mixed_args(self):
        a = self.A(1, b=2)
        assert a.a == 1 and a.b == 2

    def test_equality(self):
        a1 = self.A(1, 2)
        a2 = self.A(1, 2)
        a3 = self.LikeA(1, 2)
        different = self.B(2)
        different2 = self.A(2, 2)

        assert a1 == a1
        assert a1 == a2 and a2 == a1
        assert a1 == a3 and a3 == a1
        assert a1 != different and different != a1
        assert a1 != different2 and different2 != a1
        assert a1 != (1, 2)


def test_snapshot_item_serialization_roundtrip():
    path = '  some \n /weird \t path '
    status = create_file_status()
    a = SnapshotItem('key', path, status)
    ser = a.serialize()
    b = SnapshotItem.parse(ser)
    assert a == b


def test_commit_serialization_roundtrip():
    a = Commit(123.45, 'snapshot', 'message', None)
    ser = a.serialize()
    b = Commit.parse(ser)
    assert a == b


def test_branch_serialization_roundtrip():
    a = Branch(64 * 'a')
    ser = a.serialize()
    b = Branch.parse(ser)
    assert a == b


def test_reference_with_commit_serialization_roundtrip():
    a = Reference(Reference.COMMIT, 64 * 'a')
    ser = a.serialize()
    b = Reference.parse(ser)
    assert a == b


def test_reference_with_branch_serialization_roundtrip():
    a = Reference(Reference.BRANCH, 'branch_name')
    ser = a.serialize()
    b = Reference.parse(ser)
    assert a == b


class TestFridgeCore(object):
    def _create_snapshot(self):
        return [
            SnapshotItem(
                checksum='a1b2', path='a', status=create_file_status()),
            SnapshotItem(
                checksum='cd34', path='b', status=create_file_status())
        ]

    def test_snapshot_roundtrip(self):
        snapshot = [
            SnapshotItem('key1', ' \n\t/weird path \n', create_file_status()),
            SnapshotItem('key2', '\n another path', create_file_status())]
        serialized = FridgeCore.serialize_snapshot(snapshot)
        parsed = FridgeCore.parse_snapshot(serialized)
        assert snapshot == parsed

    def test_add_blob_and_checkout_blob(self, fs, fridge_core):
        write_file(fs, 'path', u'content')
        key = fridge_core.add_blob('path')
        assert not fs.exists('path')
        fridge_core.checkout_blob(key, 'path')
        assert fs.get_node(['path']).content.decode() == u'content'

    def test_writing_and_reading_snapshot(self, fs):
        s = self._create_snapshot()

        fridge = FridgeCore.init(os.curdir, fs)
        key = fridge.add_snapshot(s)
        del fridge

        fridge = FridgeCore(os.curdir, fs)
        assert s == fridge.read_snapshot(key)

    def test_writing_two_snapshots(self, fs):
        s1 = self._create_snapshot()
        s2 = [SnapshotItem('key', 'xyz', create_file_status())]

        fridge = FridgeCore.init(os.curdir, fs)
        key1 = fridge.add_snapshot(s1)
        key2 = fridge.add_snapshot(s2)
        assert s1 == fridge.read_snapshot(key1)
        assert s2 == fridge.read_snapshot(key2)

    def test_setting_and_getting_head(self, fs):
        fridge = FridgeCore.init(os.curdir, fs)
        fridge.set_head(Reference(Reference.COMMIT, u'ab12cd'))
        del fridge

        fridge = FridgeCore(os.curdir, fs)
        assert fridge.get_head() == Reference(Reference.COMMIT, u'ab12cd')
        assert fridge.get_head_key() == u'ab12cd'

    def test_setting_and_getting_branch(self, fs):
        fridge = FridgeCore.init(os.curdir, fs)
        fridge.set_branch('test_branch', u'ab12cd')
        del fridge

        fridge = FridgeCore(os.curdir, fs)
        assert fridge.is_branch('test_branch')
        assert fridge.resolve_branch('test_branch') == u'ab12cd'

    def test_checkout_blob_on_checkedout(self, fs, fridge_core):
        write_file(fs, 'mockfile', u'content')
        key = fridge_core.add_blob('mockfile')
        fridge_core.checkout_blob(key, 'mockfile')
        fridge_core.checkout_blob(key, 'mockfile')
        assert fs.get_node(['mockfile']).content.decode() == u'content'


class TestFridge(object):
    def test_commit_and_checkout(self, fridge, fs):
        write_file(fs, 'mockfile', u'content')
        status = fs.stat('mockfile')
        fridge.commit(message='msg')
        fs.unlink('mockfile')
        fridge.checkout()
        assert fs.get_node(['mockfile']).content.decode() == u'content'
        assert fs.stat('mockfile') == status

    def test_log(self):
        commits = [
            ('headhash', Commit(2., 'snapshot2', 'msg2', 'c1')),
            ('c1', Commit(1., 'snapshot1', 'msg1', 'c0')),
            ('c0', Commit(0., 'snapshot0', 'msg0', None))]
        commit_dict = {}
        for (k, v) in commits:
            commit_dict[k] = v
        fs = MagicMock()
        core_mock = MagicMock()
        core_mock.get_head_key.return_value = 'headhash'
        core_mock.read_commit.side_effect = lambda k: commit_dict[k]

        assert commits == Fridge(core_mock, fs).log()

    def test_refparse_commit(self, fridge, fridge_core, fs):
        write_file(fs, 'mockfile')
        fridge.commit()
        ref = fridge_core.get_head()
        assert ref.type == Reference.BRANCH
        assert fridge.refparse(ref.ref) == ref
        key = fridge_core.resolve_branch(ref.ref)
        assert fridge.refparse(key) == Reference(Reference.COMMIT, key)

    def test_refparse_with_ambiguous_ref(self, fridge, fridge_core, fs):
        write_file(fs, 'mockfile')
        fridge.commit()
        key = fridge_core.get_head_key()
        fridge.branch(key)
        with pytest.raises(AmbiguousReferenceError):
            fridge.refparse(key)

    def test_refparse_with_nonexisting_ref(self, fridge):
        with pytest.raises(UnknownReferenceError):
            fridge.refparse('foo')

    def test_branch_sets_new_head(self, fridge, fridge_core, fs):
        write_file(fs, 'mockfile')
        fridge.commit()
        assert fridge_core.get_head() == Reference(Reference.BRANCH, 'master')
        fridge.branch('branch')
        assert fridge_core.get_head() == Reference(Reference.BRANCH, 'branch')

    def test_branch_exists(self, fridge, fs):
        write_file(fs, 'mockfile')
        fridge.commit()
        fridge.branch('branch')
        with pytest.raises(BranchExistsError):
            fridge.branch('branch')

    def test_diff(self, fridge, fs):
        write_file(fs, 'remove')
        write_file(fs, 'update', u'ver1')
        write_file(fs, 'unchanged', u'foobar')
        fridge.commit()
        fs.unlink('remove')
        write_file(fs, 'update', u'ver2')
        write_file(fs, 'new')

        result = fridge.diff()
        assert result.removed == ['remove']
        assert result.updated == ['update']
        assert result.added == ['new']

    # TODO prevent empty commit
