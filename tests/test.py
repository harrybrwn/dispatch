#!/usr/bin/env python


# flake8: noqa: E402

import sys
from os import path

sys.path.insert(0, path.split(sys.path[0])[0])

import unittest
from dispatch.dispatch import Command, command, _parse_flags_doc
from dispatch.flags import _from_typing_module, _is_iterable, Option
from dispatch._meta import _FunctionMeta
from dispatch.exceptions import UserException

from typing import List, Set, Dict, Sequence, Mapping
import types


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


class SomeClass:
    def cmd(self, hello: str, switch: bool, what='hello'):
        ''':hello: say hello'''
        print('method command')
        print(self)

    @classmethod
    def class_cmd(cls, hello: str, switch: bool, what='hello'):
        ''':hello: say hello'''
        print('classmethod command')

    @staticmethod
    def static_cmd(hello: str, switch: bool, what='hello'):
        ''':hello: say hello'''
        print('staticmethod command')


class TestCommand(unittest.TestCase):

    def test(self): ...

    class FlagType:
        def __init(self, name):
            self.name = name

    EMPTY_HELP = expected = 'Usage:\n    {name} [options]\n\nOptions:\n    -h, --help   Get help.' # noqa

    def testGeneralCommand(self):
        self.assertTrue(some_cli is not None)

    def testcommand(self):
        CFG_FILE = '/home/user/.local/etc/config.cfg'
        @command(hidden={'debug'})
        def cli(*args, verbose: bool, debug=False, off=False, config: str = CFG_FILE):
            self.assertFalse(config is None)
            self.assertEqual(config, CFG_FILE)
        cli([])

    def testCommand(self):
        def fn(arg1, arg2): pass
        cmd = Command(fn)
        self.assertEqual(cmd.name, 'fn')
        self.assertEqual(cmd.flags['arg1'].name, 'arg1')
        self.assertEqual(cmd.flags['arg2'].name, 'arg2')
        self.assertIs(cmd.flags['arg1'].type, bool)
        self.assertIs(cmd.flags['arg1'].type, bool)

    def testEmptyCommand(self):
        def fn(): pass
        cmd = Command(fn)
        self.assertEqual(len(cmd.flags), 0)
        self.assertEqual(cmd.name, 'fn')

        @command
        def run(): pass
        run()

    def testOptionTypes(self):
        def fn(a: str, b: int, c: bool, d: self.FlagType, pi=3.14159): pass
        cmd = Command(fn)
        flags = cmd.flags
        self.assertEqual(len(cmd.flags), 5)
        self.assertEqual(flags['a'].type, str)
        self.assertEqual(flags['b'].type, int)
        self.assertEqual(flags['c'].type, bool)
        self.assertEqual(flags['d'].type, self.FlagType)
        self.assertEqual(flags['pi'].type, float)

    def testDocParsing(self):
        def fn(verbose=False, pi=3.14159, tag: str = ''):
            '''fn is a function
            that has a multi-line description.
            :v verbose:
            : pi  : this is the value of pi




            :      t              tag :this is a tag

            '''
        parsed = _parse_flags_doc(fn.__doc__)
        self.assertTrue('verbose' in parsed)
        self.assertEqual(parsed['verbose']['shorthand'], 'v')
        self.assertTrue('pi' in parsed)
        self.assertTrue(parsed['pi']['shorthand'] is None)
        self.assertEqual(parsed['tag']['doc'], "this is a tag")

        cmd = Command(fn)
        self.assertEqual(
            cmd._help, "fn is a function\nthat has a multi-line description.")
        self.assertEqual(len(cmd.flags), 3)
        f = cmd.flags['verbose']
        self.assertEqual(f.name, 'verbose')
        self.assertEqual(f.shorthand, 'v')
        self.assertEqual(f.type, bool)
        self.assertEqual(f.value, False)
        self.assertEqual(cmd.flags['pi'].type, float)
        self.assertEqual(cmd.flags['pi'].value, 3.14159)
        self.assertEqual(cmd.flags['pi'].help, 'this is the value of pi')
        self.assertEqual(cmd.flags['tag'].type, str)
        self.assertEqual(cmd.flags['tag'].help, 'this is a tag')
        self.assertEqual(cmd.flags['tag'].shorthand, 't')
        self.assertEqual(cmd.flags['tag'].value, '')
        self.assertEqual(cmd.flags['t'].name, 'tag')
        self.assertEqual(cmd.flags['t'].type, str)
        self.assertEqual(cmd.flags['t'].help, 'this is a tag')
        self.assertEqual(cmd.flags['t'].shorthand, 't')
        self.assertEqual(cmd.flags['t'].value, '')
        self.assertEqual(cmd.flags['t'], cmd.flags['tag'])
        self.assertEqual(id(cmd.flags['t']), id(cmd.flags['tag']))

        self.assertTrue(cmd.flags['verbose'].has_default)
        self.assertEqual(cmd.flags['verbose'].value, False)
        self.assertTrue(cmd.flags['pi'].has_default)
        self.assertEqual(cmd.flags['pi'].value, 3.14159)
        self.assertTrue(cmd.flags['tag'].has_default)
        self.assertEqual(cmd.flags['tag'].value, '')

        hlp = cmd.helptext()
        for name, flag in cmd.flags.items():
            self.assertIn(name, hlp)
            self.assertIn(flag.help, hlp)

    def testIncompleteDocParsing(self):
        def fn(verbose: bool, hello):
            ''':l hello: say hello'''
            pass
        cmd = Command(fn)
        self.assertTrue(cmd.flags['l'] is not None)
        self.assertEqual(cmd.flags['l'].name, 'hello')
        self.assertIn('-l, --hello', cmd.helptext())

        @command
        def fn2(verbose: bool, hello):
            ''':l hello: say hello'''
        self.assertIn('-l, --hello', fn2.helptext())

    def testBadDoc(self):
        def f1(verbose: bool): pass
        cmd = Command(f1)
        htext = cmd.helptext()
        expected = 'Usage:\n    f1 [options]\n\nOptions:\n        --verbose   \n    -h, --help      Get help.' # noqa
        self.assertTrue(htext and len(htext) > 5)
        self.assertEqual(expected, cmd.helptext())

        def f2(): pass
        cmd = Command(f2)
        htext = cmd.helptext()
        self.assertTrue(htext and len(htext) > 5)
        self.assertEqual(self.EMPTY_HELP.format(name='f2'), htext)

    def testRunCommand(self):
        def fn(name: str):
            '''
            :n name: give the program a name
            '''
            self.assertEqual(name, 'joe')
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
            self.assertEqual(name, 'joe')
            return len(fn2.flags)
        r = fn2(['--name', 'joe'])
        self.assertTrue(r == 1)
        r = fn2(['-n', 'joe'])
        self.assertTrue(r == 1)
        r = fn2(['--name=joe'])
        self.assertTrue(r == 1)
        r = fn2(['-n=joe'])
        self.assertTrue(r == 1)

        @command()
        def fn3(multi_word_flag, bool_flag: bool):
            self.assertTrue(multi_word_flag)
            self.assertFalse(bool_flag)
        fn3(['--multi-word-flag'])  # pylint: disable=no-value-for-parameter

    def testCommandSettings(self):
        @command(
            hidden={'debug', 'verbose'},
            defaults={'debug': False})
        def f1(debug: bool, verbose: bool):
            ''':v verbose:'''
            exp = self.EMPTY_HELP.format(name='f1')
            got = f1.helptext()
            self.assertEqual(exp, got)
            self.assertTrue(verbose)
            self.assertFalse(debug)
            return 76
        val = f1(['-v'])  # pylint: disable=no-value-for-parameter
        self.assertEqual(val, 76)
        self.assertEqual(str(f1), f1.helptext())

        @command(shorthands={'debug': 'd'},
                 help="f2 is a test command")
        def f2(debug: bool = False):
            self.assertTrue(debug)
            return 'what???'
        val = f2(['-d'])
        self.assertEqual(val, 'what???')
        self.assertIn('f2 is a test command', f2.helptext())
        self.assertEqual(str(f2), f2.helptext())

        @command(doc_help=True, allow_null=True)
        def f3(some_string: str):
            '''this is the raw documentation
-h, --help'''
            self.assertTrue(some_string is None)
        self.assertEqual(
            f3.helptext(), 'this is the raw documentation\n-h, --help')
        f3()  # pylint: disable=no-value-for-parameter

    def testFormat(self):
        pass

    def testMeta(self):
        self.skipTest('this feature isnt finished')
        sc = SomeClass()
        funcs = [sc.cmd, sc.class_cmd, sc.static_cmd, SomeClass.static_cmd]
        for f in funcs:
            m = _FunctionMeta(f)
            self.assertEqual(m.params()[0], 'hello')
            self.assertEqual(m.name, f.__name__)
            self.assertEqual(m.doc, f.__doc__)

    def testHelp(self):
        got = some_cli.helptext()
        h = '''Some_cli is just some generic cli tool
that has a multi-line description.'''
        self.assertIn(h, got)
        self.assertTrue(got.startswith(h))
        self.assertIn('-f, --file', got)
        self.assertIn('Give the cli a file', got)
        self.assertIn('-v, --verbose', got)
        self.assertIn('Print out all the information to stdout', got)
        self.assertIn('--time', got)
        self.assertIn('Use some other time (default: local)', got)
        self.assertIn('-o, --output', got)
        self.assertIn('Give the program an output file (default: stdout)', got)
        self.assertIn('-h, --help', got)

    def testArgParsing(self):
        @command
        def cli(file: str, verbose: bool, time: str = 'local',
                debug: bool = False, output: str = 'stdout'):
            self.assertTrue(isinstance(debug, bool))
            self.assertTrue(debug)
            self.assertTrue(len(cli.args) > 0)
            self.assertEqual(cli.args[0], 'argument')

        cli(['--debug', 'argument'])  # pylint: disable=no-value-for-parameter
        self.assertEqual(len(cli.args), 1)
        cli(['argument', '--debug'])  # pylint: disable=no-value-for-parameter
        self.assertEqual(len(cli.args), 1)
        cli(['--debug', 'argument'])  # pylint: disable=no-value-for-parameter
        self.assertEqual(len(cli.args), 1)
        cli(['argument', '-debug',  # pylint: disable=no-value-for-parameter
             'a value', '-verbose',
             'another-value', '--time', 'now'])
        self.assertEqual(cli.args, ['argument', 'a value', 'another-value'])
        self.assertRaises(UserException,
            cli, ['argument', '-debug', '--time']
        )


class TestOptions(unittest.TestCase):

    class AType:
        def __init__(self, val):
            self.val = val

    def testTypeParsing(self):
        o = Option('o', List[int])
        o.setval('[1,2,3,4]')
        self.assertTrue(isinstance(o.value, list))
        for got, want in zip(o.value, [1, 2, 3, 4]):
            self.assertTrue(isinstance(got, int))
            self.assertTrue(isinstance(want, int))
            self.assertEqual(got, want)

        o = Option('o', list)
        o.setval('[1,2,3,4]')
        self.assertTrue(isinstance(o.value, list))
        for got, want in zip(o.value, [1, 2, 3, 4]):
            self.assertTrue(isinstance(got, str))
            self.assertTrue(isinstance(want, int))
            self.assertEqual(int(got), want)
            self.assertEqual(got, str(want))

        o = Option('o', Set[float])
        o.setval('[1.5,2.6,3.7,4.8]')
        self.assertTrue(isinstance(o.value, set))
        for got, want in zip(o.value, [1.5, 2.6, 3.7, 4.8]):
            self.assertTrue(isinstance(got, float))
            self.assertTrue(isinstance(want, float))
            self.assertEqual(got, want)
            self.assertEqual(got, want)

        o = Option('o', Dict[str, int])
        o.setval('{one:1,two:2,three:3}')
        self.assertTrue(isinstance(o.value, dict))
        for k, v in o.value.items():
            self.assertTrue(isinstance(k, str))
            self.assertTrue(isinstance(v, int))

        opt = Option('num', complex)
        opt.setval('5+9j')
        self.assertEqual(opt.value, complex(5, 9))
        opt.setval(complex(7, 2))
        self.assertEqual(opt.value, complex(7, 2))
        opt.setval(6.7)
        self.assertEqual(opt.value, complex(6.7, 0))

        opt = Option('type', self.AType)
        opt.setval('hello')
        self.assertTrue(isinstance(opt.value, self.AType))
        self.assertEqual(opt.value.val, 'hello')

    def testBadTypeParsing(self):
        o = Option('outout', Dict[str, float])
        self.assertRaises(
            ValueError, o.setval,
            '{one:1.0,two:2.5,three:the third number,four:4}')

        opt = Option('num', complex)
        self.assertRaises(ValueError, opt.setval, '4+3i')

        @command()
        def f(keys: Dict[str, float]):
            pass
        self.assertRaises(
            ValueError, f, ['--keys', '{one:1,two:this is the number two}'])


class TestFlagSet(unittest.TestCase):
    def testInit(self): pass


class TestHelpers(unittest.TestCase):
    def testIsIterable(self):
        self.assertTrue(_is_iterable(str))
        self.assertTrue(_is_iterable(list))
        self.assertTrue(_is_iterable(dict))
        self.assertTrue(_is_iterable(set))
        self.assertTrue(_is_iterable(List))
        self.assertTrue(_is_iterable(Dict))
        self.assertTrue(_is_iterable(Sequence))
        self.assertTrue(_is_iterable(Mapping))
        class A: pass # noqa
        self.assertFalse(_is_iterable(int))
        self.assertFalse(_is_iterable(float))
        self.assertFalse(_is_iterable(A))

        self.assertTrue(_is_iterable([1, 2, 3]))

    def testFromTypingModule(self):
        self.assertTrue(_from_typing_module(List))
        self.assertTrue(_from_typing_module(Sequence))
        self.assertTrue(_from_typing_module(Dict[int, str]))
        self.assertFalse(_from_typing_module(list))
        self.assertFalse(_from_typing_module(int))
        self.assertFalse(_from_typing_module(dict))
        class A: pass # noqa
        self.assertFalse(_from_typing_module(A))


class TestMeta(unittest.TestCase):
    def testFunctionMeta(self):
        import inspect

        def f(*args, name: str, verbose, file='/dev/null'):
            var = 'hello'
            new_const = 55
            self.assertEqual(('one', 'two', 3, complex(4)), args)

        m = _FunctionMeta(f)
        self.assertEqual(m.run, f.__call__)
        self.assertEqual(m.annotations, f.__annotations__)

        self.assertEqual(m.params(), ('name', 'verbose', 'file'))
        posargs = ['one', 'two', 3, complex(4)]
        kwds = {
            'name': 'jim',
            'verbose': True,
            'file': '/dev/null',
        }

        self.assertTrue(m.has_variadic_param())
        f(*posargs, **kwds)
        CFG_FILE = '/home/user/.local/etc/config.cfg'
        def cli(*args, verbose: bool, debug=False, off=False, config: str = CFG_FILE):
            pass
        m = _FunctionMeta(cli)
        self.assertEqual(len(m.defaults()), 3)
        self.assertEqual(m.defaults()['config'], CFG_FILE)

    def testClassFuncs(self):
        print()
        c = SomeClass()
        m = _FunctionMeta(c.cmd)
        self.assertTrue(isinstance(m.obj, types.MethodType))
        m = _FunctionMeta(c.class_cmd)
        self.assertTrue(isinstance(m.obj, types.MethodType))
        m = _FunctionMeta(c.static_cmd)
        self.assertFalse(isinstance(m.obj, types.MethodType))


if __name__ == '__main__':
    unittest.main()


def bench():
    from timeit import timeit
    from string import ascii_letters
    setup = 'from string import ascii_letters; args = list(ascii_letters)'
    # setup = "args = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']"
    print('pop(0):        ', timeit('''
a = args[:]
while a:
    arg = a.pop(0)
''', setup=setup))
    print('pop():         ', timeit('''
a = args[:]
while a:
    arg = a.pop()
''', setup=setup))
    print('reversed pop():', timeit('''
a = list(reversed(args))
while a:
    arg = a.pop()
''', setup=setup))
