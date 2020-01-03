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

    @abstractmethod
    def annotations(self): ...

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

        self.code = code or obj.__code__
        self.signature = inspect.signature(self.obj)
        self.name = name or obj.__name__
        self.doc = doc or obj.__doc__
        self._annotations = annotations or obj.__annotations__
        self._defaults = defaults or obj.__defaults__
        self.instance = instance
        self.helpstr, self.flagdocs = self._parse_doc(self.doc)

        if self.instance or isinstance(self.obj, MethodType):
            self.needs_self = True
        else:
            self.needs_self = False

    def run(self, *args, **kwrgs):
        if self.needs_self and self.instance is not None:
            return self.obj.__call__(self.instance, *args, **kwrgs)
        return self.obj.__call__(*args, **kwrgs)

    def params(self):
        v = self.code.co_varnames
        end = self.code.co_argcount + self.code.co_kwonlyargcount
        start = 1 if self.needs_self else 0 # exclude self
        return v[start:end]

    def annotations(self):
        return self._annotations

    def has_variadic_param(self) -> bool:
        params = list(self.signature.parameters.values())
        if not params:
            return False
        for p in params:
            if p.kind == inspect.Parameter.VAR_POSITIONAL:
                return True
        return False

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
        for typ in self._annotations.values():
            if is_dataclass(typ):
                return True
        return False

    def get_dataclass(self) -> tuple:
        for name, typ in self._annotations.items():
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
    def __init__(self, obj, instance=None):
        self.obj = obj
        self.doc = obj.__doc__
        self._defaults = {}

        if hasattr(obj, '__annotations__'):
            self._annotations = obj.__annotations__
        else:
            self._annotations = {}

        attrs = self.obj.__class__.__dict__

        for name, attr in attrs.items():
            if (
                not name.startswith('_') and
                not _isfunc(attr) and
                attr != type.mro
            ):
                self._annotations[name] = type(attr)
                self._defaults[name] = attr
        self.helpstr, self.flagdocs = self._parse_doc(self.doc)

    def flagnames(self) -> set:
        names = set()
        names.update(self._annotations.keys(), self._defaults.keys())
        return names

    def run(self):
        raise NotImplementedError('')

    def params(self) -> tuple:
        raise NotImplementedError

    def defaults(self):
        return self._defaults

    def annotations(self):
        return self._annotations


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