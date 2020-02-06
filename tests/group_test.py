import pytest
from pytest import raises

import sys
import os
from os.path import dirname
sys.path.insert(0, dirname(dirname(__file__)))

from dispatch import command, subcommand, Group, Command, UserException
from dispatch.dispatch import _find_commands, SubCommand
from dispatch.exceptions import BadFlagError
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
    @command(**{'init': dict(one=1, two=2, three=3)})
    class cmd:
        def __init__(self, *, one: int, two: int, three: int):
            assert one == 1
            assert two == 2
            assert three == 3

@pytest.mark.xfail
def test_group_init_fail_2():
    @command
    class cmd:
        def __init__(self, an_arg): ...

def test_hidden():
    settings = dict(
        hidden={"hidden", 'sub_command'},
        shorthands={'value': 'v'},
        hidden_defaults={'value'},
    )
    @command(**settings)
    class c:
        hidden: bool
        value: str = 'secret_key'
        def sub_command(self): ...
        def go_do_it(self):
            '''go do that thing'''
            assert self.hidden

        @subcommand(hidden=True)
        def hidden_command(self, flagval=False):
            assert flagval
            assert self.hidden

    hlp = c.helptext()

    assert '--hidden' not in hlp
    assert 'secret_key' not in hlp
    assert '-v, --value' in hlp
    assert 'sub_command' not in hlp
    assert 'hidden_command' not in hlp
    c(['hidden_command', '--flagval', '--hidden'])
    assert c.inst.hidden
    c._reset()
    assert not c.inst.hidden
    c(['--hidden', 'go-do-it'])
    c._reset()
    c(['go-do-it', '--hidden'])
    c._reset()
    for f in c.inst.hidden_command.flags.values():
        f._reset()
    with raises(AssertionError):
        c(['hidden_command', '--hidden'])
    c._reset()
    for f in c.inst.hidden_command.flags.values():
        f._reset()
    with raises(AssertionError):
        c(['hidden_command', '--flagval'])

def test_group_parseargs():
    @command
    class cmd:
        def __call__(self):
            assert cmd.args == ['one', 'two']
    cmd(['one', 'two'])
    assert cmd.args == ['one', 'two']
    cmd._reset()
    assert cmd.args == []

def test_group_err(capsys):
    def f(a): ...

    sysexit = sys.exit
    sys.exit = f
    @command
    class cmd:
        verbose: bool

    # with raises(TypeError):
    #     cmd([])

    sys.exit = sysexit
    hlp = cmd.helptext()
    assert 'Commands:' not in hlp
    with raises(BadFlagError, match="'notaflag' is not a flag"):
        cmd(['--notaflag'])

@pytest.mark.xfail
def test_function():
    def func(arg, kwd=None):
        ...
    func(**{'arg': 'what', 'kwd': 5, 'another': 'what'})


def test_subcommand():
    @command
    class cmd:
        @subcommand
        def inner(self):
            '''hello'''
            ...
        @subcommand
        def func(self):
            '''i am a func'''
            ...
    hlp = cmd.helptext()
    assert SubCommand.__doc__[:15].strip() not in hlp

def test_command_aliases():
    @command
    class cmd:
        def inner(self):
            '''hello'''
        def func(self):
            '''i am a func'''
        function = func

    hlp = cmd.helptext()
    print(hlp)
