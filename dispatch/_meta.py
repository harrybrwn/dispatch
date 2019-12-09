from dataclasses import is_dataclass
import types
import inspect


class _FunctionMeta:
    '''Not a metaclass, the 'meta' means 'meta-data'.'''
    def __init__(self, obj, name=None, doc=None,
                 code=None, defaults=None, annotations=None):
        self.obj = obj
        self.run = obj.__call__
        self.name = name or obj.__name__
        self.doc = doc or obj.__doc__
        self.code = code or obj.__code__
        self._defaults = defaults or obj.__defaults__
        self.annotations = annotations or obj.__annotations__
        self._params_start = 0
        self.signature = inspect.signature(self.obj)

    def _type_checking(self, obj):
        '''
        This is not being used yet it is mostly expirimental but is a
        draft for the future.
        '''
        if isinstance(obj, (classmethod, staticmethod)):
            self._cmd_obj = obj.__func__
            self._params_start = 1
        elif isinstance(obj, types.MethodType):
            self._cmd_obj = obj
            self._params_start = 1
        else:
            self._cmd_obj = obj
            self._params_start = 0

    def params(self):
        v = self.code.co_varnames
        end = self.code.co_argcount + self.code.co_kwonlyargcount
        return v[self._params_start:end]

    def has_variadic_param(self):
        params = list(self.signature.parameters.values())
        if not params:
            return False
        return params[0].kind == inspect.Parameter.VAR_POSITIONAL

    def has_params(self):
        params = list(self.signature.parameters)
        return bool(params)

    def defaults(self) -> dict:
        args = reversed(self.params())
        defs = reversed(self._defaults or [])
        return dict(zip(args, defs))

    def has_dataclass(self) -> bool:
        for typ in self.annotations.values():
            if is_dataclass(typ):
                return True
        return False

    def get_dataclass(self) -> tuple:
        for name, typ in self.annotations.items():
            if is_dataclass(typ):
                return name, typ
        return '', None
