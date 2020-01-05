import pytest
from pytest import raises

import sys
from os.path import dirname, realpath
sys.path.insert(0, dirname(dirname(realpath(__file__))))

from dispatch.exceptions import UserException, DeveloperException
from dispatch.dispatch import Command, command
from dispatch._meta import _parse_flags_doc, _FunctionMeta

def test_command():
    CFG_FILE = '/home/user/.local/etc/config.cfg'
    @command(hidden={'debug'})
    def cli(*args, verbose: bool, debug=False,
            off=False, config: str = CFG_FILE):
        assert config is not None
        assert config == CFG_FILE
        assert len(args) == 0
    cli([])

    @command
    def run(): pass
    run([])

def test_Command():
    def fn(arg1, arg2): pass
    cmd = Command(fn)
    assert cmd._meta.name == 'fn'
    assert cmd.flags['arg1'].name == 'arg1'
    assert cmd.flags['arg2'].name == 'arg2'
    assert cmd.flags['arg1'].type is bool
    assert cmd.flags['arg1'].type is bool

    def fn(): pass
    cmd = Command(fn)
    assert len(cmd.flags) == 0
    assert cmd._meta.name == 'fn'

class FlagType:
        def __init(self, name):
            self.name = name

def testOptionTypes():
    def fn(a: str, b: int, c: bool, d: FlagType, pi=3.14159): pass
    cmd = Command(fn)
    flags = cmd.flags
    assert len(cmd.flags) == 5
    assert flags['a'].type is str
    assert flags['b'].type is int
    assert flags['c'].type is bool
    assert flags['d'].type is FlagType
    assert flags['pi'].type is float

def testDocParsing():
    def fn(verbose=False, pi=3.14159, tag: str = ''):
        '''fn is a function
        that has a multi-line description.
        :v verbose:
        : pi  : this is the value of pi




        :      t              tag :this is a tag

        '''
    parsed = _parse_flags_doc(fn.__doc__)
    assert 'verbose' in parsed
    assert parsed['verbose']['shorthand'] == 'v'
    assert 'pi' in parsed
    assert parsed['pi']['shorthand'] is None
    assert parsed['tag']['doc'] == "this is a tag"

    cmd = Command(fn)
    assert "fn is a function" in cmd._help
    assert "that has a multi-line description." in cmd._help
    assert len(cmd.flags) == 3
    f = cmd.flags['verbose']
    assert f.name == 'verbose'
    assert f.shorthand == 'v'
    assert f.type is bool
    assert f.value is False
    assert cmd.flags['pi'].type is float
    assert cmd.flags['pi'].value == 3.14159
    assert cmd.flags['pi'].help == 'this is the value of pi'
    assert cmd.flags['tag'].type is str
    assert cmd.flags['tag'].help == 'this is a tag'
    assert cmd.flags['tag'].shorthand == 't'
    assert cmd.flags['tag'].value == ''
    assert cmd.flags['t'].name == 'tag'
    assert cmd.flags['t'].type is str
    assert cmd.flags['t'].help == 'this is a tag'
    assert cmd.flags['t'].shorthand == 't'
    assert cmd.flags['t'].value == ''
    assert cmd.flags['t'] == cmd.flags['tag']
    assert id(cmd.flags['t']) == id(cmd.flags['tag'])

    assert cmd.flags['verbose'].has_default
    assert cmd.flags['verbose'].value == False
    assert cmd.flags['pi'].has_default
    assert cmd.flags['pi'].value == 3.14159
    assert cmd.flags['tag'].has_default
    assert cmd.flags['tag'].value == ''

    hlp = cmd.helptext()
    for name, flag in cmd.flags.items():
        assert name in hlp
        assert flag.help in hlp

def test_incomplete_doc_parsing():
    def fn(verbose: bool, hello):
        ''':l hello: say hello'''
        pass
    cmd = Command(fn)
    assert cmd.flags['l'] is not None
    assert cmd.flags['l'].name == 'hello'
    assert '-l, --hello' in cmd.helptext()
    assert 'say hello' in cmd.helptext()

    @command
    def fn2(verbose: bool, hello):
        ''':l hello: say hello'''
    assert '-l, --hello' in fn2.helptext()
    assert 'say hello' in fn2.helptext()

EMPTY_HELP = 'Usage:\n    {name} [options]\n\nOptions:\n    -h, --help   Get help.'

def test_bad_doc():
    def f1(verbose: bool): pass
    cmd = Command(f1)
    htext = cmd.helptext()
    assert 'Usage:\n    f1 [options]' in htext
    assert '--verbose' in htext
    assert '-h, --help' in  htext
    assert 'Get help.' in htext
    expected = 'Usage:\n    f1 [options]\n\nOptions:\n        --verbose   \n    -h, --help      Get help.' # noqa
    assert htext and len(htext) > 5
    assert expected == cmd.helptext()

    def f2(): pass
    cmd = Command(f2)
    htext = cmd.helptext()
    assert htext and len(htext) > 5
    assert EMPTY_HELP.format(name='f2') == htext

def test_run_Command():
    def fn(name: str):
        '''
        :n name: give the program a name
        '''
        assert name == 'joe'
    cmd = Command(fn)
    cmd.run(['--name', 'joe'])
    cmd.run(['-n', 'joe'])
    cmd.run(['--name=joe'])
    cmd.run(['-n=joe'])

    @command
    def fn2(name: str):
        '''
        :n name: give the program a name
        '''
        assert name == 'joe'
        return len(fn2.flags)
    r = fn2(['--name', 'joe'])
    assert r == 1
    r = fn2(['-n', 'joe'])
    assert r == 1
    r = fn2(['--name=joe'])
    assert r == 1
    r = fn2(['-n=joe'])
    assert r == 1

    @command()
    def fn3(multi_word_flag, bool_flag: bool):
        assert multi_word_flag
        assert not bool_flag
    fn3(['--multi-word-flag'])  # pylint: disable=no-value-for-parameter

def test_command_settings():
    @command(
        hidden={'debug', 'verbose'},
        defaults={'debug': False})
    def f1(debug: bool, verbose: bool):
        ''':v verbose:'''
        exp = EMPTY_HELP.format(name='f1')
        got = f1.helptext()
        assert exp == got
        assert verbose
        assert not debug
        return 76
    val = f1(['-v'])  # pylint: disable=no-value-for-parameter
    assert val == 76
    assert str(f1) == f1.helptext()

    @command(shorthands={'debug': 'd'},
             help="f2 is a test command")
    def f2(debug: bool = False):
        assert debug
        return 'what???'
    val = f2(['-d'])
    assert val == 'what???'
    assert 'f2 is a test command' in f2.helptext()
    assert str(f2) == f2.helptext()

    @command(doc_help=True, allow_null=True)
    def f3(some_string: str):
        '''this is the raw documentation
-h, --help'''
        assert some_string is None
    assert f3.helptext() == 'this is the raw documentation\n-h, --help'
    f3([])  # pylint: disable=no-value-for-parameter

def test_variadic_command():
    @command
    def f(*args, thing: str, doit: bool):
        assert len(args) > 1
        assert args[0] == 'one'
        assert args[1] == 'two'
        if not doit:
            raise Exception("expected do-it")
    f(['one', 'two', '--doit'])

@command(hidden={'debug'})
def some_cli(file: str, verbose: bool, time: str = 'local',
             debug: bool = False, output: str = 'stdout'):
    '''Some_cli is just some generic cli tool
    that has a multi-line description.

    :f file:    Give the cli a file
    :v verbose: Print out all the information to stdout
    :time:      Use some other time
    :o output:  Give the program an output file
    '''
    assert time is not None
    assert output is not None

def testHelp():
    got = some_cli.helptext()
    assert got.startswith('Some_cli is just some generic cli tool\n')
    tc = [
        'Some_cli is just some generic cli tool\n',
        'that has a multi-line description.\n',
        '-f, --file',    'Give the cli a file\n',
        '-v, --verbose', 'Print out all the information to stdout\n',
        '--time',        'Use some other time (default: local)\n',
        '-o, --output',  'Give the program an output file (default: stdout)\n',
        '-h, --help',
    ]
    for t in tc:
        assert t in got

def testArgParsing():
    @command
    def cli(file: str, verbose: bool, time: str = 'local',
            debug: bool = False, output: str = 'stdout'):
        assert isinstance(debug, bool)
        assert debug
        assert len(cli.args) > 0
        assert cli.args[0] == 'argument'

    cli(['--debug', 'argument'])  # pylint: disable=no-value-for-parameter
    assert len(cli.args) == 1
    cli(['argument', '--debug'])  # pylint: disable=no-value-for-parameter
    assert len(cli.args) == 1
    cli(['--debug', 'argument'])  # pylint: disable=no-value-for-parameter
    assert len(cli.args) == 1
    cli(['argument', '-debug',  # pylint: disable=no-value-for-parameter
         'a value', '-verbose',
         'another-value', '--time', 'now'])
    assert cli.args == ['argument', 'a value', 'another-value']
    with raises(UserException):
        cli(['argument', '-debug', '--time'])

def test_none_command():
    with raises(DeveloperException):
        c = Command(None)