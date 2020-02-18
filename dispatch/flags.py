import sys
from typing import Dict, Optional
from collections.abc import Iterable
from dataclasses import is_dataclass

from .exceptions import DeveloperException
from ._meta import _FunctionMeta, _GroupMeta, _CliMeta


class Option:

    __slots__ = ('name', 'type', 'shorthand', 'help', '_value',
                 'hidden', '_default', 'has_default', 'f_len', 'hide_default')

    def __init__(self, name, typ, *,
                 shorthand: str = None, help: str = None, value=None,
                 hidden=False, has_default=False, hide_default=False):
        self.name = name
        self.type = typ if typ is not None else bool

        self.shorthand = shorthand
        self.help = help or ''
        self.value = value  # will infer and set the type

        self.hidden = hidden
        self._default = value
        self.has_default = has_default or value is not None
        self.hide_default = hide_default
        self.f_len = len(self.name)  # len(name) is temp, will be set when formatting

        if self.shorthand == 'h' and self.name != 'help':
            raise DeveloperException(
                "cannot use 'h' as shorthand (reserved for --help)")

    def __format__(self, spec: str):
        name_spec = f'<{self.f_len}'
        prefix = ''
        if spec:
            if '<' in spec:
                name_spec = '<' + spec[spec.index('<') + 1]
            elif '>' in spec:
                name_spec = '>' + spec[spec.index('>') + 1]
            if '+' in spec:
                prefix = ' ' * int(spec[spec.index('+')+1])

        if self.shorthand:
            short = f'-{self.shorthand}, '
        else:
            short = ' ' * 4

        return '{0}{short}--{name:{1}}{help}{default}'.format(
            prefix, name_spec, short=short,
            name=self.name.replace('_', '-'),
            help=self.help,
            default=self.show_default(),
        )

    def __repr__(self):
        return "{}('{}', {})".format(
            self.__class__.__name__, str(self).strip(), self.type)

    def __str__(self):
        if self.shorthand:
            return '-{}, --{}'.format(self.shorthand, self.name)
        else:
            return '     --{}'.format(self.name)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        if val is not None:
            self.type = val.__class__

    def show_default(self) -> str:
        if self.has_default and not self.hide_default and self.value:
            if self.help:
                return f' (default: {self.value!r})'
            else:
                return f'default: {self.value!r}'
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
            # if the type is a string, we dont need to convert it
            self._value = val
        else:
            if _is_iterable(self.type):
                val = val.strip('[]{}').split(',')

            if _from_typing_module(self.type):
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

    def _getnull(self):
        '''_getnull will return a null value given the flag's type.
        If there is a default value, that will be returned.
        '''
        if self.has_default:
            return self._default

        try:
            return self.type()
        except TypeError:
            # if the constructory needs an argument
            # then we cant do much so return None
            return None

    def _reset(self):
        self._value = self._getnull()


class FlagSet:
    '''A Set of cli Flags'''

    DEFAULT_HELP_FLAG = Option('help', bool, shorthand='h', help='Get help.')
    MIN_FMT_LEN = 3

    __slots__ = ('_flags', '_flagnames', '_shorthands')

    def __init__(self, *, names: tuple = None, defaults: dict = None,
                 docs: dict = None, types: dict = None,
                 shorthands: dict = None, hidden: set = set(), **kwrgs):
        '''
        Create a FlagSet

            names:      `list` of flag names, use only the fullnames
            defaults:   `dict` of default flag values
            docs:       `dict` of default flag help text
            types:      `dict` of type annotations
            shorthands: `dict` of flag shorthands. Give it in the format
                {<flagname>: <shorthand>} but know that the copy stored in the
                flag set will also store flagnames in the format
                {<shorthand>: <flagname>}.
            hidden: `set` of the flagnames that will be hidden from the help
                text of the FlagSet.
            hidden_defaults: `set` of flags that should not show their defauts
        '''
        self._flags: Dict[str, Option] = {}
        self._flagnames = names or ()
        self._shorthands = shorthands or dict()

        types = types or dict()
        defaults = defaults or dict()
        docs = docs or dict()
        hidden_defaults = kwrgs.pop('hidden_defaults', set())

        cmd_meta: Optional[_CliMeta] = kwrgs.pop('__command_meta__')
        if cmd_meta:
            if not isinstance(cmd_meta, _CliMeta):
                raise TypeError('__command_meta__ should inherit from _meta._CliMeta')

            for key, val in cmd_meta.flagdocs.items():
                self._shorthands[key] = val.get('shorthand')
                docs[key] = val.get('doc')
            types.update(cmd_meta.annotations())
            defaults.update(cmd_meta.defaults())

        for name in self._flagnames:
            opt = Option(
                name, types.get(name, bool),
                shorthand=self._shorthands.get(name),
                help=docs.get(name, ''),
                value=defaults.get(name),
                hidden=name in hidden,
                hide_default=name in hidden_defaults,
            )
            self[name] = opt

    @property
    def format_len(self) -> int:
        fmt_len = max([len(f.name) for f in self.visible_flags()])
        return fmt_len + self.MIN_FMT_LEN

    @property
    def help(self) -> str:
        fmt = '    {0:<{1}}'
        lngth = self.format_len
        return '\n'.join(fmt.format(f, lngth) for f in self.visible_flags())

    def __str__(self):
        return str(self._flags)

    def __len__(self):
        return len(self._flags)

    def __getitem__(self, key) -> Option:
        if len(key) == 1 and key in self._shorthands:
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

    def __contains__(self, key) -> bool:
        return key in self._flags or key in self._shorthands

    def __iter__(self):
        return iter(self._flags)

    def items(self):
        yield from self._flags.items()

    def values(self):
        yield from self._flags.values()

    def update(self, fset=None):
        if not isinstance(fset, FlagSet):
            raise TypeError(
                'must update {0} with a {0}'.format(self.__class__.__name__))
        self._flags.update(fset._flags)
        self._shorthands.update(fset._shorthands)

    def get(self, key: str, default=None) -> Option:
        try:
            return self[key]
        except KeyError:
            return default

    def visible_flags(self):
        yield from (
            flag for flag in self._flags.values()
            if not flag.hidden
        )
        yield self.DEFAULT_HELP_FLAG


def _from_typing_module(t) -> bool:
    if hasattr(t, '__module__'):
        mod = t.__module__
        import typing
        return sys.modules[mod] == typing
    return False


def _is_iterable(t) -> bool:
    if _from_typing_module(t):
        return issubclass(t.__origin__, Iterable)
    return isinstance(t, Iterable) or issubclass(t, Iterable)
