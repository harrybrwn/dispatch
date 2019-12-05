#!/usr/bin/python

import unittest
from dispatch import dispatch

class TestCommand(unittest.TestCase):
    class FlagType:
        def __init(self, name):
            self.name = name

    EMPTY_HELP = expected = 'Usage:\n    {name} [options]\n\nOptions:\n    -h, --help       Get help.'

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
        def fn(verbose=False, pi=3.14159, tag: str=''):
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
        self.assertEqual(cmd._help, "fn is a function\nthat has a multi-line description.")
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

    def testBadDoc(self):
        def f1(verbose: bool): pass
        cmd = dispatch.Command(f1)
        htext = cmd.helptext()
        expected = 'Usage:\n    f1 [options]\n\nOptions:\n        --verbose    \n    -h, --help       Get help.'
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

        @dispatch.command()
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

    def testCommandSettings(self):
        @dispatch.command(hidden={'debug', 'verbose'}, defaults={'debug': False})
        def f1(debug: bool, verbose: bool):
            ''':v verbose:'''
            exp = self.EMPTY_HELP.format(name='f1')
            got = f1.helptext()
            self.assertEqual(exp, got)
            self.assertTrue(verbose)
            self.assertTrue(len(f1.hidden) == 2)
            self.assertTrue(len(f1.defaults) == 1)
            return 76
        val = f1(['-v'])
        self.assertEqual(val, 76)

        @dispatch.command(shorthands={'debug': 'd'})
        def f2(debug: bool=False):
            self.assertTrue(len(f2.shorthands) == 1)
            self.assertTrue(debug)
            return 'what???'
        val = f2(['-d'])
        self.assertEqual(val, 'what???')

class TestOptions(unittest.TestCase):
    def testTypeParsing(self):
        from typing import List, Set, Sequence, Dict

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
        for got, want in zip(o.value, [1.5,2.6,3.7,4.8]):
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
        from typing import Dict

        o = dispatch.Option('outout', Dict[str, float])
        self.assertRaises(ValueError, o.setval, '{one:1.0,two:2.5,three:the third number,four:4}')
        @dispatch.command()
        def f(keys: Dict[str, float]):
            pass
        self.assertRaises(ValueError, f, ['--keys', '{one:1,two:this is the number two}'])


class TestHelpers(unittest.TestCase):
    def testIsIterable(self):
        from typing import List, Dict, Sequence, Mapping
        from dispatch.dispatch import _is_iterable
        self.assertTrue(_is_iterable(str))
        self.assertTrue(_is_iterable(list))
        self.assertTrue(_is_iterable(dict))
        self.assertTrue(_is_iterable(set))
        self.assertTrue(_is_iterable(List))
        self.assertTrue(_is_iterable(Dict))
        self.assertTrue(_is_iterable(Sequence))
        self.assertTrue(_is_iterable(Mapping))
        class A: pass
        self.assertFalse(_is_iterable(int))
        self.assertFalse(_is_iterable(float))
        self.assertFalse(_is_iterable(A))

        import inspect
        inspect.isbuiltin
        self.assertTrue(_is_iterable([1, 2, 3]))

    def testFromTypingModule(self):
        from dispatch.dispatch import _from_typing_module
        from typing import List, Sequence, Dict
        self.assertTrue(_from_typing_module(List))
        self.assertTrue(_from_typing_module(Sequence))
        self.assertTrue(_from_typing_module(Dict[int, str]))
        self.assertFalse(_from_typing_module(list))
        self.assertFalse(_from_typing_module(int))
        self.assertFalse(_from_typing_module(dict))
        class A: pass
        self.assertFalse(_from_typing_module(A))

def expiriments():
    def func(name, *args): pass
    # def func(name, *, args=None): pass
    import inspect
    from inspect import signature

    def lookat(x, prefix="_"):
        for a in dir(x):
            if not a.startswith(prefix):
                attr = getattr(x, a)
                print(a, attr, type(attr))

    sig = signature(func)
    args = sig.parameters['args']
    print(args)
    print(type(args))
    lookat(args)

if __name__ == '__main__':
    unittest.main()

