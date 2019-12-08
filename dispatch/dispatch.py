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
import types
import jinja2

from .flags import Option, FlagSet
from ._funcmeta import _FunctionMeta
from .exceptions import UserException, DeveloperException, RequiredFlagError


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


class _Command:
    '''Command Base class'''
    def __init__(self, callback, meta: _FunctionMeta):
        '''
        callback: callable object that will be run when command is executed.
        meta: meta information an the callback object
        '''
        self.callback = callback
        self._meta = meta


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

        self._meta = _FunctionMeta(
            self.callback,
            name=self.callback.__name__,
            doc=self.callback.__doc__,
            code=self.callback.__code__,
            defaults=self.callback.__defaults__,
            annotations=self.callback.__annotations__
        )

        self.flagnames = self._meta.params()
        self.defaults = self._meta.defaults()
        self.name = self._meta.name

        self._help, flagdoc = parse_doc(self._meta.doc)
        self.shorthands = {}
        self.docs = {}
        for key, val in flagdoc.items():
            self.shorthands[key] = val.get('shorthand')
            self.docs[key] = val.get('doc')

        self._help = kwrgs.get('help', self._help)
        self.help_template = kwrgs.get('help_template', HELP_TMPL)
        self.hidden = kwrgs.get('hidden', set())
        self.doc_help = kwrgs.get('doc_help', False)
        self.allow_null = kwrgs.get('allow_null', True)

        self.shorthands.update(kwrgs.get('shorthands', {}))
        self.docs.update(kwrgs.get('docs', {}))
        self.defaults.update(kwrgs.get('defaults', {}))

        self.args = []
        self.flags = self._find_flags()

        # checking the Command settings for validity
        # raises error if there is an invalid setting
        check_names = kwrgs.get('check_names', True)
        if check_names:
            self._check_flag_settings()

    def __call__(self, argv=sys.argv):
        if argv is sys.argv:
            argv = argv[1:]
        if '--help' in argv or '-h' in argv:
            return self.help()

        fn_args = self.parse_args(argv)
        return self._meta.run(**fn_args)

    def __repr__(self):
        return f'{self.__class__.__name__}({self._meta.name}())'

    def __str__(self):
        return self.helptext()

    def _flag_lengths(self, flags=[]):
        return max([len(f.name) for f in flags or self.visible_flags()]) + 3

    @property
    def _flag_help(self):
        flags = list(self.visible_flags())
        flen = self._flag_lengths(flags)
        return '\n'.join(['    {1:<{0}}'.format(flen, f) for f in flags])

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
                self._meta.annotations.get(name),
                shorthand=self.shorthands.get(name),
                help=self.docs.get(name),
                value=self.defaults.get(name),
                hidden=name in self.hidden,
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

    def visible_flags(self):
        helpflag = Option('help', bool, shorthand='h', help='Get help.')
        for name, flag in self.flags.items():
            if (len(name) == 1 and flag.shorthand) or flag.hidden:
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


def helptext(fn):
    return Command(fn).helptext()


def command(_fn=None, **kwrgs):
    def cmd(fn):
        return Command(fn, **kwrgs)

    # command is being called with parens as @command(...)
    if _fn is None:
        return cmd

    # being called without parens as @command
    return cmd(_fn)



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
