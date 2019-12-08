import sys
import typing
from collections.abc import Iterable
from dataclasses import is_dataclass

from .exceptions import DeveloperException
from ._funcmeta import _FunctionMeta

class Option:
    def __init__(self, name, typ, *,
                 shorthand=None, help=None, value=None,
                 hidden=None, has_default=None):
        self.name = name
        self.type = typ or bool
        self.shorthand = shorthand
        self.help = help
        self.value = value
        self.has_default = has_default
        self.hidden = hidden if hidden is not None else False
        self.f_len = len(self.name)  # temp value, should be set later

        if self.shorthand == 'h' and self.name != 'help':
            raise DeveloperException(
                "cannot use 'h' as shorthand (reserved for --help)")

    def __format__(self, spec):
        return '{short}--{name:{0}}{help}'.format(
            f'<{self.f_len}' if not spec else spec,
            short=f'-{self.shorthand}, ' if self.shorthand else ' ' * 4,
            name=self.name.replace('_', '-'),
            help=self.help or '')

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        if val is not None:
            self.type = val.__class__

    def show_default(self) -> str:
        if not self.has_default:
            return ''
        elif self.type is not bool and self.value:
            return f'(default: {self.value})'
        elif self.type is bool:
            return f'(default: {self.value})'
        return ''

    def setval(self, val):
        '''
        setval is meant to be used to set the value of the flag from the
        cli input and convert it to the flag's type. setval should also work
        when the flag.type is a compound type annotation (see typing package).

        This function is basically a rich type convertion. Any flag types that
        are part of the typing package will be converted to the python type it
        represents.

        Another feature of the is function is allowing an option to take more
        complex arguments such as lists or dictionaries.
        '''
        # TODO: type checking does not work if the annotation is an abstract
        #       base class. (collections.abc.Sequence etc..)

        if not isinstance(val, str) or self.type is str:
            # if val is not a string then the type has already been converted
            self._value = val
        else:
            if _is_iterable(self.type) and self.type is not str:
                val = val.strip('[]{}').split(',')

            if self.type is str:
                self._value = val
            elif _from_typing_module(self.type):
                if len(self.type.__args__) == 1:
                    inner = self.type.__args__[0]
                    self._value = self.type.__origin__([inner(v) for v in val])
                elif len(self.type.__args__) == 2:
                    key_tp, val_tp = self.type.__args__
                    vals = []
                    for vl in val:
                        k, v = vl.split(':')
                        pair = key_tp(k), val_tp(v)
                        vals.append(pair)
                    self._value = self.type.__origin__(vals)
            else:
                self._value = self.type(val)

    def __repr__(self):
        return "{}('{}', {})".format(
            self.__class__.__name__, str(self), self.type)

    def __str__(self):
        if self.shorthand:
            return '-{}, --{}'.format(self.shorthand, self.name)
        else:
            return '     --{}'.format(self.name)

    def __len__(self):
        '''Get the length of the option name when formatted in the help text
        eg. same as `len('-v, --verbose') or `len('    --verbose')``
        '''
        length = len(self.name) + 2  # plus len of '--'
        if self.shorthand:
            length += 4  # length of '-v, ' if v is the shorthand
        return length


class FlagSet:
    '''A Set of cli Flags'''

    DEFAULT_HELP_FLAG = Option('help', bool, shorthand='h', help='Get help.')

    def __init__(self, *, obj=None, names: list = None,
                 defaults: dict = None, docs: dict = None,
                 shorhands: dict = None):
        '''
        Create a FlagSet

            obj:      create a new FlagSet from an object (usually a dataclass)
            names:    `list` of flag names, use only the fullnames
            defaults: `dict` of default flag values
            docs:     `dict` of default flag help text
            types:    `dict` of type annotations
        '''
        self._flags = {}
        self._flagnames = names or []
        self._shorthands = shorhands or {}
        self._defaults = defaults or {}
        self._docs = docs or {}

        # Now find out what the obj is and use it to update the
        # flag data
        if obj is None: # this is the most likly case
            return
        elif isinstance(obj, _FunctionMeta):
            pass
        elif is_dataclass(obj):
            pass

    def __getitem__(self, key):
        if len(key) == 1:
            key = self._shorthands[key]
        return self._flags[key]

    def __setitem__(self, key, flag):
        self._flags[key] = flag
        if flag.shorthand:
            self._shorthands[flag.shorthand] = key

    def __delitem__(self, key):
        raise NotImplementedError

    def __contains__(self, key):
        return key in self._flags or key in self._shorthands

    def items(self):
        for name, flag in self._flags.items():
            yield name, flag

    def visible_flags(self):
        for name, flag in self.flags.items():
            if (len(name) == 1 and flag.shorthand) or flag.hidden:
                continue
            yield flag
        yield self.DEFAULT_HELP_FLAG


def _from_typing_module(t) -> bool:
    if hasattr(t, '__module__'):
        mod = t.__module__
        return sys.modules[mod] == typing
    return False

def _is_iterable(t) -> bool:
    if _from_typing_module(t):
        return issubclass(t.__origin__, Iterable)
    return isinstance(t, Iterable) or issubclass(t, Iterable)
