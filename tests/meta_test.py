import pytest, sys
from os.path import dirname
sys.path.insert(0, dirname(dirname(__file__)))

import types

from dispatch._meta import _FunctionMeta, _CliMeta
from dispatch.dispatch import Command

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

def testMeta():
    sc = SomeClass()
    funcs = [sc.cmd, sc.class_cmd, sc.static_cmd, SomeClass.static_cmd]
    for f in funcs:
        m = _FunctionMeta(f)
        assert m.params()[0] == 'hello'
        assert m.name == f.__name__
        assert m.doc == f.__doc__
    def cli(*args, verbose: bool, debug=False,
            off=False, config: str = '.config'): ...
    m = _FunctionMeta(cli)
    assert m.name == 'cli'
    assert m.has_variadic_param() == True
    assert m.has_params()

def testFunctionMeta():
    def f(*args, name: str, verbose, file='/dev/null'):
        var = 'hello'
        new_const = 55
        assert ('one', 'two', 3, complex(4)) == args

    m = _FunctionMeta(f)
    assert m.annotations() == f.__annotations__

    assert m.params() == ('name', 'verbose', 'file')
    posargs = ['one', 'two', 3, complex(4)]
    kwds = {
        'name': 'jim',
        'verbose': True,
        'file': '/dev/null',
    }

    assert m.has_variadic_param()
    f(*posargs, **kwds)
    CFG_FILE = '/home/user/.local/etc/config.cfg'
    def cli(*args, verbose: bool, debug=False, off=False, config: str = CFG_FILE):
        pass
    m = _FunctionMeta(cli)
    assert len(m.defaults()) == 3
    assert m.defaults()['config'] == CFG_FILE

def testClassFuncs():
    c = SomeClass()
    m = _FunctionMeta(c.cmd)
    assert isinstance(m.obj, types.MethodType)
    m = _FunctionMeta(c.class_cmd)
    assert isinstance(m.obj, types.MethodType)
    m = _FunctionMeta(c.static_cmd)
    assert not isinstance(m.obj, types.MethodType)

def test_multi_name_flag_docs():
    def f(flag_name, another_flag):
        '''this is a cli

        :f flag-name: a flag's name
        :a another_flag: another flag
        '''
    c = Command(f)
    assert '-f, --flag-name' in c.helptext()
    assert '-a, --another-flag' in c.helptext()