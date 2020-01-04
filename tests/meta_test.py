import pytest, sys
from os.path import dirname, realpath
sys.path.insert(0, dirname(dirname(realpath(__file__))))

from dispatch._meta import _FunctionMeta

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

import types

def testClassFuncs():
    c = SomeClass()
    m = _FunctionMeta(c.cmd)
    assert isinstance(m.obj, types.MethodType)
    m = _FunctionMeta(c.class_cmd)
    assert isinstance(m.obj, types.MethodType)
    m = _FunctionMeta(c.static_cmd)
    assert not isinstance(m.obj, types.MethodType)

