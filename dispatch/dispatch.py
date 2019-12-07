# Copyright © 2019 Harrison Brown harrybrown98@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from collections.abc import Iterable
import typing
import jinja2

__all__ = ['Command', 'UserException', 'helptext', 'command', 'handle']


HELP_TMPL = '''{%- if main_doc -%}
{{ main_doc }}

{% endif -%}
Usage:
    {{ name }} [options]

Options:
{%- for flg in flags %}
    {{ '{}'.format(flg) }}
    {%- if flg.has_default %}{{ flg.show_default() }}{% endif %}
{%- endfor %}
'''


class Command:

    def __init__(self, callback, **kwrgs):
        # note: docs are modified at runtime
        '''
        Args:
            callback: a function that runs the command

        Keyword Args:
            shorthands (dict): Give the command flags a shorthand use
                {<flag name>: <shorthand>}, has greater precedence over doc
                parsing.
            docs (dict): Give the command flags a doc string use
                {<flag name>: <help text>} has greater precedence over doc
                parsing.
            defaults (dict): Give the command flags a default value use
                {<flag name>: <value>} has greater precedence over doc parsing.
            hidden (set):  The set of flag names that should be hidden.

            help: (str):        Command's main description.
            doc_help (bool): If True (default is False), use the callback
                __doc__ as the help text for this command.
            help_template (str): template used for the help text
                to have a value of None. This would mean that none of the
                command's flags are required.
            allow_null (bool):  If True (default is True), flags are allowed
            check_names (bool): If True (default is True), the Command will
                check all the flag names given in any command settings or
                function docs to see if they are valid flags.
        '''
        self.callback = callback
        if not callable(self.callback):
            raise DeveloperException('Command callback needs to be callable')
        meta = self.callback.__code__
        self.flagnames = meta.co_varnames[:meta.co_argcount]
        self.name = self.callback.__name__

        self._help, flagdoc = parse_doc(self.callback.__doc__)
        self.shorthands = {}
        self.docs = {}
        for key, val in flagdoc.items():
            self.shorthands[key] = val.get('shorthand')
            self.docs[key] = val.get('doc')

        self.defaults = dict(
            zip(reversed(self.flagnames),
                reversed(self.callback.__defaults__ or []))
        )

        self._help = kwrgs.get('help') or self._help
        self.help_template = kwrgs.get('help_template') or HELP_TMPL
        self.hidden = kwrgs.get('hidden') or set()
        self.doc_help = kwrgs.get('doc_help') or False
        self.allow_null = kwrgs.get('allow_null') or True

        self.shorthands.update(kwrgs.get('shorthands') or {})
        self.docs.update(kwrgs.get('docs') or {})
        self.defaults.update(kwrgs.get('defaults') or {})

        self.args = []
        self.flags = self._find_flags()

        # checking the Command settings for validity
        # raises error if there is an invalid setting
        check_names = kwrgs.get('check_names')
        check_names = True if check_names is None else check_names
        if check_names:
            self._check_flag_settings()

    def __call__(self, argv=sys.argv):
        if argv is sys.argv:
            argv = argv[1:]
        if '--help' in argv or '-h' in argv:
            return self.help()

        fn_args = self.parse_args(argv)
        return self.callback(**fn_args)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.callback.__name__}())'

    def __str__(self):
        return self.helptext()

    def _flag_lengths(self, flags=[]):
        return max([len(f.name) for f in flags or self.visible_flags()]) + 3

    @property
    def _flag_help(self):
        fmt = '    {1:<{0}}'
        flags = list(self.visible_flags())
        flen = self._flag_lengths(flags)
        return '\n'.join([fmt.format(flen, f) for f in flags])

    def help(self):
        print(self.helptext())

    def helptext(self) -> str:
        if self.doc_help:
            return self.callback.__doc__

        flags = list(self.visible_flags())

        fmt_len = max([len(f.name) for f in flags]) + 3
        for f in flags:
            f.f_len = fmt_len

        tmpl = jinja2.Template(self.help_template)
        return tmpl.render({
            'main_doc': self._help,
            'name': self.name,
            'flags': flags,
        })

    def _find_flags(self):
        flags = {}
        for name in self.flagnames:
            opt = Option(
                name,
                self.callback.__annotations__.get(name),
                shorthand=self.shorthands.get(name),
                help=self.docs.get(name),
                value=self.defaults.get(name),
                hidden=True if name in self.hidden else False,
                has_default=name in self.defaults
            )
            flags[name] = opt
            if opt.shorthand:
                flags[opt.shorthand] = opt
        return flags

    def _check_flag_settings(self):
        flagchecks = set()
        if self.defaults:
            flagchecks.update(self.defaults.keys())
        if self.shorthands:
            flagchecks.update(self.shorthands.keys())
        if self.docs:
            flagchecks.update(self.docs.keys())
        # check all the flags being modified by the command settings
        for f in flagchecks:
            if f not in self.flagnames:
                raise DeveloperException(f'{f} is not a flag')

    def _named_flags(self) -> dict:
        return {key: val for key, val in self.iter_named_flags()}

    def iter_named_flags(self):
        for name, flag in self.flags.items():
            if len(name) == 1 and flag.name in self.flags:
                continue
            yield name, flag

    def visible_flags(self) -> list:
        helpflag = Option('help', bool, shorthand='h', help='Get help.')
        for flag in self.flags.values():
            if flag.shorthand or flag.hidden:
                continue
            yield flag
        yield helpflag

    def parse_args(self, args: list) -> dict:
        '''
        Parse a list of strings and return a dictionary of function arguments.
        The return values is supposd to be unpacked and used as an argument
        to the Command's callback function.
        '''
        args = args[:]
        while args:
            arg = args.pop(0)
            if arg[0] != '-':
                self.args.append(arg)
                continue

            arg = arg.lstrip('-').replace('-', '_')

            val = None
            if '=' in arg:
                arg, val = arg.split('=')
            elif args and args[0][0] != '-':
                # if the next arg is not a flag then it is the flag val
                val = args.pop(0)

            flag = self.flags.get(arg)
            if not flag:
                raise UserException("could not find flag '{}'".format(arg))

            if val is not None:
                # If the flag has been given a value but
                # has no type (aka. NoneType) then we should
                # assume it is a string.
                if flag.type is None.__class__:
                    flag.type = str
                flag.setval(val)
            elif flag.type is bool:
                flag.value = True if flag.value is None else not flag.value

        if self.allow_null:
            return {n: f.value for n, f in self.iter_named_flags()}
        return self._null_check_flag_args()

    def run(self, argv=sys.argv):
        return self.__call__(argv)

    def _null_check_flag_args(self) -> dict:
        values = {}
        for name, flag in self.iter_named_flags():
            # all flags should have a value at this point
            # if not, booleans are false all else raises an error
            if not flag.has_default and flag.value is None:
                if flag.type is bool:
                    flag.value = False
                else:
                    raise RequiredFlagError(
                        f"'--{flag.name}' is a required flag")
            values[name] = flag.value
        return values


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
        cli input and convert it to the flag's type. setval should work
        when the flag.type is a compound type annotation (see typing package).

        This function is basically a rich type convertion. Any flag types that
        are part of the typing package will be converted to the python type it
        represents.
        '''
        # TODO: type checking does not work if the annotation is an abstract
        #       base class.

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


def parse_doc(docstr: str) -> tuple:
    if docstr is None:
        return '', {}
    if docstr.count(':') < 2:
        desc = docstr
        flags = {}
    else:
        i = docstr.index(':')
        desc = docstr[:i]
        flags = _parse_flags_doc(docstr[i:])

    doc = '\n'.join([l.strip() for l in desc.split('\n') if l])
    return doc.strip(), flags


class UserException(Exception):
    pass


class DeveloperException(Exception):
    pass


class RequiredFlagError(UserException):
    pass


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


def _from_typing_module(t) -> bool:
    if hasattr(t, '__module__'):
        mod = t.__module__
        return sys.modules[mod] == typing
    return False


def _is_iterable(t) -> bool:
    if _from_typing_module(t):
        return issubclass(t.__origin__, Iterable)
    return isinstance(t, Iterable) or issubclass(t, Iterable)


def helptext(fn):
    return Command(fn).helptext()


def command(**kwrgs):
    def runner(fn):
        return Command(fn, **kwrgs)
    return runner


def handle(fn):
    try:
        fn()
    except UserException as e:
        print('Error:', e, file=sys.stderr)
        exit(1)


command.__doc__ = f'''
    Decrotator that creates a Command
{Command.__init__.__doc__}'''

Command.__init__.__doc__ = f'''
    Iinitialze a new Command
{Command.__init__.__doc__}'''
