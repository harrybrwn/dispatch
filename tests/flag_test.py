import pytest
from pytest import raises

import sys
from os.path import dirname
sys.path.insert(0, dirname(dirname(__file__)))

from typing import List, Set, Dict, Sequence, Mapping

from dispatch import command
from dispatch.flags import Option, _from_typing_module, _is_iterable

class AType:
    def __init__(self, val):
        self.val = val

def testTypeParsing():
    o = Option('o', List[int])
    o.setval('[1,2,3,4]')
    assert isinstance(o.value, list)
    for got, want in zip(o.value, [1, 2, 3, 4]):
        assert isinstance(got, int)
        assert isinstance(want, int)
        assert got == want

    o = Option('o', list)
    o.setval('[1,2,3,4]')
    assert isinstance(o.value, list)
    for got, want in zip(o.value, [1, 2, 3, 4]):
        assert isinstance(got, str)
        assert isinstance(want, int)
        assert int(got) == want
        assert got == str(want)

    o = Option('o', Set[float])
    o.setval('[1.5,2.6,3.7,4.8]')
    assert isinstance(o.value, set)
    for got, want in zip(o.value, [1.5, 2.6, 3.7, 4.8]):
        assert isinstance(got, float)
        assert isinstance(want, float)
        assert got == want
        assert got == want

    o = Option('o', Dict[str, int])
    o.setval('{one:1,two:2,three:3}')
    assert isinstance(o.value, dict)
    for k, v in o.value.items():
        assert isinstance(k, str)
        assert isinstance(v, int)

    opt = Option('num', complex)
    opt.setval('5+9j')
    assert opt.value == complex(5, 9)
    opt.setval(complex(7, 2))
    assert opt.value == complex(7, 2)
    opt.setval(6.7)
    assert opt.value == complex(6.7, 0)

    opt = Option('type', AType)
    opt.setval('hello')
    assert isinstance(opt.value, AType)
    assert opt.value.val == 'hello'

def testBadTypeParsing():
    o = Option('outout', Dict[str, float])
    opt = Option('num', complex)
    @command
    def f(keys: Dict[str, float]):
        pass

    with raises(ValueError):
        o.setval('{one:1.0,two:2.5,three:the third number,four:4}')
        opt.setval('4+3i')
        f(['--keys', '{one:1,two:this is the number two}'])

def testIsIterable():
    assert _is_iterable(str)
    assert _is_iterable(list)
    assert _is_iterable(dict)
    assert _is_iterable(set)
    assert _is_iterable(List)
    assert _is_iterable(Dict)
    assert _is_iterable(Sequence)
    assert _is_iterable(Mapping)
    class A: pass # noqa
    assert not _is_iterable(int)
    assert not _is_iterable(float)
    assert not _is_iterable(A)
    assert _is_iterable([1, 2, 3])

def testFromTypingModule():
    assert _from_typing_module(List)
    assert _from_typing_module(Sequence)
    assert _from_typing_module(Dict[int, str])
    assert not _from_typing_module(list)
    assert not _from_typing_module(int)
    assert not _from_typing_module(dict)
    class A: pass # noqa
    assert not _from_typing_module(A)

