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