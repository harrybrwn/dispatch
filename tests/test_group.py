import pytest
from pytest import raises

import sys
from os.path import dirname, realpath
sys.path.insert(0, dirname(dirname(realpath(__file__))))

from dispatch import command, Group, Command, UserException
from dispatch.dispatch import _find_commands
from dispatch._meta import _isgroup, _isfunc, _GroupMeta


def testGroup():
    @command
    class cmd: ...
    assert isinstance(cmd, Group)
    @command
    def cmd(): ...
    assert isinstance(cmd, Command)

def testGroupInit():
    class C:
        a_value: bool = False
        filename: str

        def c1(self): ... # print(self.filename)
        def c2(self): ...
        @classmethod
        def clsmthd(cls): ...
        @staticmethod
        def stticmthd(): ...
        def __call__(self):
            C.a_value = True

    assert _isgroup(C)
    assert _isgroup(C())
    assert not _isgroup(C.c1)
    assert not _isgroup(C.c2)
    assert _isfunc(C.c1)
    assert _isfunc(C.c2)

    g = Group(C)
    assert isinstance(g.type, type)
    assert isinstance(g.inst, g.type)
    assert not C.a_value
    g([])
    assert C.a_value

    g = Group(C())
    assert isinstance(g.type, type)
    assert isinstance(g.inst, C)
    g(['--filename=file.txt', 'c1'])

def testGroupMetaProgramming():
    class C:
        value: bool = False
        filename: str
    m = _GroupMeta(C)
    ann = m.annotations()
    assert 'value' in ann
    assert 'filename' in ann
    assert ann['value'] is bool
    assert ann['filename'] is str
    assert m.flagnames() == {'value', 'filename'}

def testArgParsing():
    @command
    class CMD:
        '''doc strings'''
        filename: str = 'nan'
        verbose: bool
        def cmd(self, flag: bool):
            '''Sub command of CMD'''
            assert self.filename == 'test.txt'
            assert flag
            assert isinstance(flag, bool)

        def other(self, flag: bool):
            '''Sub command of the CMD command'''
            assert isinstance(flag, bool)

        def hello(self, testing: str):
            '''Sub-command of CMD'''
            assert testing == 'what the heck'
            assert isinstance(testing, str)

    assert 'cmd' in CMD.commands
    assert 'hello' in CMD.commands
    assert 'other' in CMD.commands
    assert len(CMD.commands) == 3
    CMD(['cmd', '--filename=test.txt', '--flag'])
    CMD(['--filename', 'test.txt', 'cmd', '--flag'])
    CMD(['--filename=test.txt', 'cmd', '--flag'])
    CMD.args = []
    with raises(UserException):
        CMD(['other', '--flag=value'])
    CMD.args = []
    CMD(['hello', '--testing=what the heck'])
    helptxt = CMD.helptext()

    tests = [
        'CMD', '--verbose', '--filename',
        'cmd   Sub command of CMD',
        'other Sub command of the CMD command',
        'hello Sub-command of CMD',
    ]
    for t in tests:
        assert t in helptxt

def testFindCommands():
    class cmd:
        '''the doc-string'''
        val = None
        def __init__(self): ...
        def __call__(self): ...
        def one(self, value): ...
        def two(self): ...
    assert set(dict(_find_commands(cmd)).keys()) == {'one', 'two'}
    assert _isgroup(cmd)


def testTypes():
        # TODO: make this work without calling int(val)
        class thing:
            def __init__(self, val=0): self.val = int(val)

        class cmd:
            value: str
            num: float
            t: thing
            asnull: bool = False

            def __init__(self):
                self.value = 'hello'
                assert self.value == 'hello'

            def __call__(self):
                if self.asnull:
                    assert self.value == 'hello'
                    assert self.num == 0.0
                    assert self.asnull == True
                else:
                    assert self.value == 'this is a test value'
                    assert self.num == 3.14159
                    assert self.t.val == 98
                assert isinstance(self.asnull, bool)
                assert isinstance(self.value, str)
                assert isinstance(self.num, float)
                assert isinstance(self.t, thing)
        g = Group(cmd)
        g(['--asnull'])
        assert g.inst.value == 'hello'
        assert g.inst.value == 'hello'
        assert g.flags['value'].value == 'hello'
        g._reset()
        g(['--value=this is a test value', '--num=3.14159', '--t=98'])
        assert g.flags['value'].value == 'this is a test value'
        assert g.inst.value == 'this is a test value'
        assert g.flags['num'].value == 3.14159
        assert g.inst.num == 3.14159
        assert g.flags['t'].value.val == 98
        assert g.inst.t.val == 98
        g._reset()
        g(['--value', 'this is a test value', '--num', '3.14159', '-t', '98'])
        assert g.flags['value'].value == 'this is a test value'
        assert g.inst.value == 'this is a test value'
        assert g.flags['num'].value == 3.14159
        assert g.inst.num == 3.14159
        assert g.flags['t'].value.val == 98
        assert g.inst.t.val == 98
        g._reset()

def test_bool_parse():
    negate = True
    @command
    class C:
        verbose: bool
        yes: bool
        needsval: str
        def __call__(self):
            if negate:
                assert self.verbose
                assert not self.yes
            else:
                assert not self.verbose
                assert self.yes
            assert self.needsval
    C(['--verbose', '--needsval=hello'])
    negate = False
    C._reset()
    C(['--yes', '--needsval', 'this is a val'])
    with raises(UserException):
        C(['--needsval', '--verbse'])
        C(['--needsval'])
        C(['--yes=what?'])
        C(['--verbose=True'])

def test_group_init():
    @command(one=1, two=2, three=3)
    class cmd:
        def __init__(self, one, two, three):
            assert one == 1
            assert two == 2
            assert three == 3

@pytest.mark.xfail
def test_group_init_fail():
    @command(one=3, two=2, three=1)
    class cmd:
        def __init__(self, one, two, three):
            assert one == 1
            assert two == 2
            assert three == 3

@pytest.mark.xfail
def test_group_init_fail():
    @command
    class cmd:
        def __init__(self, an_arg):
            ...