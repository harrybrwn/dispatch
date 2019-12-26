from dataclasses import is_dataclass
import types
import inspect


class _FunctionMeta:
    '''Not a metaclass, the 'meta' means 'meta-data'.'''
    def __init__(self, obj, name=None, doc=None,
                 code=None, defaults=None, annotations=None):
        if isinstance(obj, (classmethod, staticmethod)):
            self.obj = obj.__func__
        else:
            self.obj = obj

        if isinstance(self.obj, (types.FunctionType, types.MethodType)):
            self.run = obj.__call__
            self.code = code or obj.__code__
        else:
            self.run = None
            self.code = None
            raise Exception('only funcitons are supported for now')

        self.signature = inspect.signature(self.obj)
        # kwd_only = self.has_variadic_param()
        self.name = name or obj.__name__
        self.doc = doc or obj.__doc__
        self.annotations = annotations or obj.__annotations__
        self._defaults = defaults or obj.__defaults__

        if isinstance(self.obj, types.MethodType):
            self._params_start = 1  # exclude 'self' or 'cls'
        else:
            self._params_start = 0

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


def _run_group(root, *, run=None, kwargs=None): ...


def _isgroup(obj) -> bool:
    return not isinstance(obj, (
        classmethod, staticmethod,
        types.FunctionType, types.MethodType
    ))
