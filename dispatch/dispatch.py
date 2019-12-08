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
import jinja2

from .flags import FlagSet
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

        self.name = self._meta.name
        self.flagnames = self._meta.params()
        self._help, flagdoc = parse_doc(self._meta.doc)

        defaults = self._meta.defaults()
        shorthands = {}
        docs = {}
        for key, val in flagdoc.items():
            shorthands[key] = val.get('shorthand')
            docs[key] = val.get('doc')

        self._help = kwrgs.get('help', self._help)
        self.help_template = kwrgs.get('help_template', HELP_TMPL)
        self.doc_help = kwrgs.get('doc_help', False)
        self.allow_null = kwrgs.get('allow_null', True)

        hidden = kwrgs.get('hidden', set())
        shorthands.update(kwrgs.get('shorthands', {}))
        docs.update(kwrgs.get('docs', {}))
        defaults.update(kwrgs.get('defaults', {}))

        self.args = []
        self.flags = FlagSet(
            names=self.flagnames,
            defaults=defaults,
            docs=docs,
            shorthands=shorthands.copy(),
            types=self.callback.__annotations__,
            hidden=hidden,
        )

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

    def help(self):
        print(self.helptext())

    def helptext(self) -> str:
        if self.doc_help:
            return self.callback.__doc__

        flags = list(self.flags.visible_flags())
        fmt_len = self.flags.format_len
        for f in flags:
            f.f_len = fmt_len

        tmpl = jinja2.Template(self.help_template)
        return tmpl.render({
            'main_doc': self._help,
            'name': self.name,
            'flags': flags,
        })

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
            return {n: f.value for n, f in self.flags.items()}
        return self._null_check_flag_args()

    def run(self, argv=sys.argv):
        return self.__call__(argv)

    def _null_check_flag_args(self) -> dict:
        values = {}
        for name, flag in self.flags.items():
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
