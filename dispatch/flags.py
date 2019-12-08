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
        self.help = help or ''
        self.value = value # will infer and set the type

        self.hidden = hidden if hidden is not None else False
        self.has_default = has_default or value is not None
        self.f_len = len(self.name)  # temp value, should be set later

        if self.shorthand == 'h' and self.name != 'help':
            raise DeveloperException(
                "cannot use 'h' as shorthand (reserved for --help)")

    def __format__(self, spec):
        if spec:
            if spec[0] == '<' or spec[0] == '>':
                name_spec = spec
        else:
            name_spec = f'<{self.f_len}'

        if self.shorthand:
            short = f'-{self.shorthand}, '
        else:
            short = ' ' * 4

        return '{short}--{name:{0}}{help}'.format(
            name_spec, short=short,
            name=self.name.replace('_', '-'),
            help=self.help)

    def __repr__(self):
        return "{}('{}', {})".format(
            self.__class__.__name__, str(self).strip(), self.type)

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


class FlagSet:
    '''A Set of cli Flags'''

    DEFAULT_HELP_FLAG = Option('help', bool, shorthand='h', help='Get help.')
    MIN_FMT_LEN = 3

    def __init__(self, *, obj=None, names: list = None,
                 defaults: dict = None, docs: dict = None,
                 shorthands: dict = None, types: dict = None,
                 hidden: set = None):
        '''
        Create a FlagSet

            obj:        create a new FlagSet from an object (usually a dataclass)
            names:      `list` of flag names, use only the fullnames
            defaults:   `dict` of default flag values
            docs:       `dict` of default flag help text
            types:      `dict` of type annotations
            shorthands: `dict` of flag shorthands. Give it in the format
                        {<flagname>: <shorthand>} but know that the copy
                        stored in the flag set will also store flagnames in
                        the format {<shorthand>: <flagname>}.
            hidden:     `set` of the flagnames that will be hidden from the
                        help text of the FlagSet.
        '''
        self._flags = {}
        self._flagnames = names or []
        self._shorthands = shorthands.copy() if shorthands else {}
        self._defaults = defaults or {}
        self._docs = docs or {}
        self._types = types or {}
        self._hidden = hidden or set()

        # Now find out what the obj is and use it to update the
        # flag data
        if obj is None: # this is the most likly case
            return
        elif isinstance(obj, _FunctionMeta):
            pass
        elif is_dataclass(obj):
            pass
        elif isinstance(obj, FlagSet):
            self.update(obj)

    @property
    def format_len(self) -> int:
        fmt_len = max([len(f.name) for f in self.visible_flags()])
        return fmt_len + self.MIN_FMT_LEN

    @property
    def _help(self):
        flags = list(self.visible_flags())
        l = self.format_len
        return '\n'.join(['    {0:<{1}}'.format(f, l) for f in flags])

    def _init_flags(self):
        for name in self._flagnames:
            opt = Option(
                name,
                self._types.get(name, bool),
                shorthand=self._shorthands.get(name),
                help=self._docs.get(name),
                value=self._defaults.get(name),
                hidden=name in self._hidden,
            )
            self._flags[name] = opt
            if opt.shorthand:
                self._shorthands[opt.shorthand] = name

    def __str__(self):
        return self._help

    def __getitem__(self, key):
        if len(key) == 1:
            key = self._shorthands[key]
        return self._flags[key]

    def __setitem__(self, key: str, flag: Option):
        self._flags[key] = flag
        if flag.shorthand:
            self._shorthands[flag.shorthand] = key

    def __delitem__(self, key):
        if len(key) == 1:
            key = self._shorthands.pop(key)
        del self._flags[key]

    def __contains__(self, key):
        return key in self._flags or key in self._shorthands

    def __iter__(self):
        return iter(self._flags)

    def items(self):
        for name, flag in self._flags.items():
            yield name, flag

    def values(self):
        for flag in self._flags.values():
            yield flag

    def update(self, fset):
        if not isinstance(fset, FlagSet):
            raise TypeError(
                'must update {0} with a {0}'.format(self.__class__.__name__))
        self._flags.update(fset._flags)
        self._shorthands.update(fset._shorthands)

    def visible_flags(self):
        for name, flag in self.flags.items():
            if flag.hidden:
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
