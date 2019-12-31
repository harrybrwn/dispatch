import sys
from dataclasses import is_dataclass
import types
from types import FunctionType, MethodType
import inspect
from abc import ABC, abstractmethod
from .exceptions import UserException


class _CliMeta(ABC):
    @abstractmethod
    def run(self, *args, **kwrgs): ...

    @abstractmethod
    def defaults(self): ...

    @abstractmethod
    def params(self): ...


def _parse_flags_doc(doc: str):
    res = {}
    s = doc[doc.index(':'):]

    for line in s.split('\n'):
        line = line.strip()

        if not line.startswith(':'):
            continue

        parsed = [l for l in line.split(':') if l]
        names = [n for n in parsed[0].split(' ') if n]

        if len(parsed) >= 2:
            tmpdoc = parsed[1].strip()
        else:
            tmpdoc = ''

        if len(names) == 2:
            res[names[1]] = {'doc': tmpdoc, 'shorthand': names[0]}
        else:
            res[names[0]] = {'doc': tmpdoc, 'shorthand': None}
    return res


class _FunctionMeta(_CliMeta):
    '''Not a metaclass, the 'meta' means 'meta-data'.'''
    def __init__(self, obj, name=None, doc=None,
                 code=None, defaults=None, annotations=None,
                 instance=None):
        if isinstance(obj, (classmethod, staticmethod)):
            self.obj = obj.__func__
        else:
            self.obj = obj

        if isinstance(self.obj, (FunctionType, MethodType)):
            self.code = code or obj.__code__
        else:
            raise Exception('only funcitons are supported')

        self.signature = inspect.signature(self.obj)
        self.name = name or obj.__name__
        self.doc = doc or obj.__doc__
        self.annotations = annotations or obj.__annotations__
        self._defaults = defaults or obj.__defaults__
        self.instance = instance
        if self.instance:
            self.needs_self = True
        else:
            self.needs_self = False

        if isinstance(self.obj, MethodType):
            self._params_start = 1  # exclude 'self' or 'cls'
        else:
            self._params_start = 0
        self.helpstr, self.flagdocs = self._parse_doc(self.doc)

    def run(self, *args, **kwrgs):
        if self.needs_self and self.instance is not None:
            return self.obj.__call__(self.instance, *args, **kwrgs)
        return self.obj.__call__(*args, **kwrgs)

    def params(self):
        v = self.code.co_varnames
        end = self.code.co_argcount + self.code.co_kwonlyargcount
        return v[self._params_start:end]

    def has_variadic_param(self) -> bool:
        params = list(self.signature.parameters.values())
        if not params:
            return False
        return params[0].kind == inspect.Parameter.VAR_POSITIONAL

    def has_params(self) -> bool:
        params = list(self.signature.parameters)
        return bool(params)

    def defaults(self) -> dict:
        names = reversed(self.params())
        vals = reversed(self._defaults or [])
        defs = dict(zip(names, vals))
        if self.obj.__kwdefaults__:
            defs.update(self.obj.__kwdefaults__)
        return defs

    def has_dataclass_param(self) -> bool:
        for typ in self.annotations.values():
            if is_dataclass(typ):
                return True
        return False

    def get_dataclass(self) -> tuple:
        for name, typ in self.annotations.items():
            if is_dataclass(typ):
                return name, typ
        return '', None

    def add_instance(self, inst):
        self.instance = inst
        self.needs_self = True

    def _parse_doc(self, docstr: str) -> tuple:
        if docstr is None:
            return '', {}
        if docstr.count(':') < 2:
            desc = docstr
            flags = {}
        else:
            i = docstr.index(':')
            desc = docstr[:i]
            flags = _parse_flags_doc(docstr[i:])

        doc = '\n'.join([l for l in desc.split('\n')])
        return doc.strip(), flags


class _GroupMeta(_CliMeta):
    def __init__(self, obj, args=None, _cmdtype=None):
        self.obj = obj
        self.name = obj.__name__
        self.doc = obj.__doc__
        self.annotations = {}
        self.args = args or sys.argv
        self._cmdtype = _cmdtype
        for arg in self.args:
            if arg == self.name:
                return

    def _find_next_command(self):
        for arg in self.args:
            func = self.obj.__dict__.get(arg)
            if func is None:
                continue
            if isinstance(func, (FunctionType, MethodType)):
                return self._cmdtype(func)
            elif isinstance(func, self._cmdtype):
                return func
        return None

    def run(self, *args, **kwrgs):
        # I know this is weird but, callable(self.obj)
        # will always return true for objects that are not class
        # instances. callable will return true if it finds __init__
        if '__call__' in dir(self.obj):
            self.obj.__call__()

        c = self._find_next_command()
        if c is None:
            raise UserException()
        return c()

    def params(self):
        return []

    def defaults(self):
        return {}

    def annotations(self):
        return {}


def _run_group(root, *, run=None, kwargs=None): ...


def _isgroup(obj) -> bool:
    return not isinstance(obj, (
        classmethod, staticmethod,
        types.FunctionType, types.MethodType
    ))

def _isfunc(obj) -> bool:
    return isinstance(obj, (
        classmethod, staticmethod,
        types.FunctionType, types.MethodType
    ))