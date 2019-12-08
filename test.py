#!/usr/bin/python

import unittest
from dispatch import dispatch
from dispatch.flags import _from_typing_module, _is_iterable

from typing import List, Set, Dict, Sequence, Mapping
from dataclasses import dataclass


@dispatch.command(hidden={'debug'})
def some_cli(file: str, verbose: bool, time: str = 'local',
             debug: bool = False, output: str = 'stdout'):
    '''Some_cli is just some generic cli tool
    that has a multi-line description.

    :f file:    Give the cli a file
    :v verbose: Print out all the information to stdout
    :time:      Use some other time
    :o output:  Give the program an output file
    '''
    pass

class TestCommand(unittest.TestCase):
    class FlagType:
        def __init(self, name):
            self.name = name

    EMPTY_HELP = expected = 'Usage:\n    {name} [options]\n\nOptions:\n    -h, --help   Get help.' # noqa

    def testGeneralCommand(self):
        self.assertTrue(some_cli is not None)

    def testCommand(self):
        def fn(arg1, arg2): pass
        cmd = dispatch.Command(fn)
        self.assertEqual(cmd.name, 'fn')
        self.assertEqual(cmd.flags['arg1'].name, 'arg1')
        self.assertEqual(cmd.flags['arg2'].name, 'arg2')
        self.assertIs(cmd.flags['arg1'].type, bool)
        self.assertIs(cmd.flags['arg1'].type, bool)

    def testEmptyCommand(self):
        def fn(): pass
        cmd = dispatch.Command(fn)
        self.assertEqual(len(cmd.flags), 0)
        self.assertEqual(cmd.name, 'fn')

        @dispatch.command
        def run(): pass
        run()

    def testOptionTypes(self):
        def fn(a: str, b: int, c: bool, d: self.FlagType, pi=3.14159): pass
        cmd = dispatch.Command(fn)
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
        parsed = dispatch._parse_flags_doc(fn.__doc__)
        self.assertTrue('verbose' in parsed)
        self.assertEqual(parsed['verbose']['shorthand'], 'v')
        self.assertTrue('pi' in parsed)
        self.assertTrue(parsed['pi']['shorthand'] is None)
        self.assertEqual(parsed['tag']['doc'], "this is a tag")

        cmd = dispatch.Command(fn)
        self.assertEqual(
            cmd._help, "fn is a function\nthat has a multi-line description.")
        self.assertEqual(len(cmd.flags), 5)
        self.assertEqual(len(cmd._named_flags()), 3)
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

    def testIncompleteDocParsing(self):
        def fn(verbose: bool, hello):
            ''':l hello: say hello'''
            pass
        cmd = dispatch.Command(fn)
        self.assertTrue(cmd.flags['l'] is not None)
        self.assertEqual(cmd.flags['l'].name, 'hello')
        self.assertIn('-l, --hello', cmd.helptext())

        @dispatch.command
        def fn2(verbose: bool, hello):
            ''':l hello: say hello'''
        self.assertIn('-l, --hello', fn2.helptext())

    def testBadDoc(self):
        def f1(verbose: bool): pass
        cmd = dispatch.Command(f1)
        htext = cmd.helptext()
        expected = 'Usage:\n    f1 [options]\n\nOptions:\n        --verbose   \n    -h, --help      Get help.' # noqa
        self.assertTrue(htext and len(htext) > 5)
        self.assertEqual(expected, cmd.helptext())

        def f2(): pass
        cmd = dispatch.Command(f2)
        htext = cmd.helptext()
        self.assertTrue(htext and len(htext) > 5)
        self.assertEqual(self.EMPTY_HELP.format(name='f2'), htext)

    def testRunCommand(self):
        def fn(name: str):
            '''
            :n name: give the program a name
            '''
            self.assertEqual(name, 'joe')
        cmd = dispatch.Command(fn)
        cmd.run(['--name', 'joe'])
        cmd.run(['-n', 'joe'])
        cmd.run(['--name=joe'])
        cmd.run(['-n=joe'])

        @dispatch.command
        def fn(name: str):
            '''
            :n name: give the program a name
            '''
            self.assertEqual(name, 'joe')
            return len(fn.flags)
        r = fn(['--name', 'joe'])
        self.assertTrue(r == 2)
        r = fn(['-n', 'joe'])
        self.assertTrue(r == 2)
        r = fn(['--name=joe'])
        self.assertTrue(r == 2)
        r = fn(['-n=joe'])
        self.assertTrue(r == 2)

        @dispatch.command()
        def fn(multi_word_flag, bool_flag: bool):
            self.assertTrue(multi_word_flag)
            self.assertFalse(bool_flag)
        fn(['--multi-word-flag'])

    def testCommandSettings(self):
        @dispatch.command(
            hidden={'debug', 'verbose'},
            defaults={'debug': False})
        def f1(debug: bool, verbose: bool):
            ''':v verbose:'''
            exp = self.EMPTY_HELP.format(name='f1')
            got = f1.helptext()
            self.assertEqual(exp, got)
            self.assertTrue(verbose)
            self.assertFalse(debug)
            self.assertTrue(len(f1.hidden) == 2)
            self.assertTrue(len(f1.defaults) == 1)
            return 76
        val = f1(['-v'])
        self.assertEqual(val, 76)
        self.assertEqual(str(f1), f1.helptext())

        @dispatch.command(shorthands={'debug': 'd'},
                          help="f2 is a test command")
        def f2(debug: bool = False):
            self.assertEqual(len(f2.shorthands), 1)
            self.assertTrue(debug)
            return 'what???'
        val = f2(['-d'])
        self.assertEqual(val, 'what???')
        self.assertIn('f2 is a test command', f2.helptext())
        self.assertEqual(str(f2), f2.helptext())

        @dispatch.command(doc_help=True, allow_null=True)
        def f3(some_string: str):
            '''this is the raw documentation
-h, --help'''
            self.assertTrue(some_string is None)
        self.assertEqual(
            f3.helptext(), 'this is the raw documentation\n-h, --help')
        f3()

    def testFormat(self):
        pass

    class SomeClass:
        def cmd(self, hello):
            ''':hello: say hello'''
            print('method command')
            print(self)

        @classmethod
        def class_cmd(cls, hello):
            ''':hello: say hello'''
            print('classmethod command')

        @staticmethod
        def static_cmd(hello):
            ''':hello: say hello'''
            print('staticmethod command')

    def testMeta(self):
        self.skipTest('this feature isnt finished')
        SomeClass = TestCommand.SomeClass
        sc = SomeClass()
        funcs = [sc.cmd, sc.class_cmd, sc.static_cmd, SomeClass.static_cmd]
        for f in funcs:
            m = dispatch.dispatch._FunctionMeta(f)
            self.assertEqual(m.params()[0], 'hello')
            self.assertEqual(m.name, f.__name__)
            self.assertEqual(m.doc, f.__doc__)


class TestOptions(unittest.TestCase):

    def testFlagSet(self):
        c = some_cli
        fset = dispatch.FlagSet(
            names=list(c.flagnames),
            defaults=c.defaults.copy(),
            docs=c.docs.copy(),
            shorthands=c.shorthands.copy(),
            types=c.callback.__annotations__.copy(),
            hidden=c.hidden.copy(),
        )
        fset._init_flags()

        for name, flag in c.flags.items():
            self.assertIn(name, fset)
            self.assertEqual(fset[name].name, c.flags[name].name)
            self.assertEqual(fset[name].help, c.flags[name].help)
            self.assertEqual(fset[name].type, c.flags[name].type)

    def testTypeParsing(self):
        o = dispatch.Option('o', List[int])
        o.setval('[1,2,3,4]')
        self.assertTrue(isinstance(o.value, list))
        for got, want in zip(o.value, [1, 2, 3, 4]):
            self.assertTrue(isinstance(got, int))
            self.assertTrue(isinstance(want, int))
            self.assertEqual(got, want)

        o = dispatch.Option('o', list)
        o.setval('[1,2,3,4]')
        self.assertTrue(isinstance(o.value, list))
        for got, want in zip(o.value, [1, 2, 3, 4]):
            self.assertTrue(isinstance(got, str))
            self.assertTrue(isinstance(want, int))
            self.assertEqual(int(got), want)
            self.assertEqual(got, str(want))

        o = dispatch.Option('o', Set[float])
        o.setval('[1.5,2.6,3.7,4.8]')
        self.assertTrue(isinstance(o.value, set))
        for got, want in zip(o.value, [1.5, 2.6, 3.7, 4.8]):
            self.assertTrue(isinstance(got, float))
            self.assertTrue(isinstance(want, float))
            self.assertEqual(got, want)
            self.assertEqual(got, want)

        o = dispatch.Option('o', Dict[str, int])
        o.setval('{one:1,two:2,three:3}')
        self.assertTrue(isinstance(o.value, dict))
        for k, v in o.value.items():
            self.assertTrue(isinstance(k, str))
            self.assertTrue(isinstance(v, int))

    def testBadTypeParsing(self):
        o = dispatch.Option('outout', Dict[str, float])
        self.assertRaises(
            ValueError, o.setval,
            '{one:1.0,two:2.5,three:the third number,four:4}')

        @dispatch.command()
        def f(keys: Dict[str, float]):
            pass
        self.assertRaises(
            ValueError, f, ['--keys', '{one:1,two:this is the number two}'])

    def testOptionFormatting(self):
        opts = [
            dispatch.Option(
                'out', bool, shorthand='o', help='Give the output'),
            dispatch.Option(
                'verbose', bool, shorthand='v', help='the verbosity'),
            dispatch.Option(
                'name', str, help='the name'),
        ]
        l = max([len(o.name)+2 for o in opts]) # noqa

    # def testFormat(self):
    #     o = dispatch.Option(
    #             'out', bool, shorthand='o', help='Give the output')
    #     print()
    #     print('{:<10}'.format(o))
    #     print('--{name}{help:>15}'.format(
    #         name='out', help='hello are you there'))
    #     print('hell{x:>6}'.format(x='hello'))


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


@dataclass
class SomeFlagSet:
    name: str
    verbose: bool


if __name__ == '__main__':
    unittest.main()

    f = SomeFlagSet('harry', True)
    # f2 = FlagSet("jim", False)
    print(dir(f))
    print()
    fields = f.__dataclass_fields__
    print(fields)
    # print(c)
    print(getattr(f, 'name'))
