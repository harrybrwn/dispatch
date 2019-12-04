#!/usr/bin/python

import unittest
import dispatch

class TestCommand(unittest.TestCase):
    class FlagType:
        def __init(self, name):
            self.name = name

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

            :v verbose:
            : pi  : this is the value of pi




            :      t              tag :

            '''
        cmd = dispatch.Command(fn)
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
        self.assertEqual(cmd.flags['tag'].help, '')
        self.assertEqual(cmd.flags['tag'].shorthand, 't')
        self.assertEqual(cmd.flags['t'].shorthand, 't')
        self.assertEqual(cmd.flags['t'].name, 'tag')
        self.assertEqual(cmd.flags['t'], cmd.flags['tag'])

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


if __name__ == '__main__':
    unittest.main()
