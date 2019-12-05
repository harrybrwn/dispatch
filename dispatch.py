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

__all__ = ['Command', 'helptext', 'command']


HELP_TMPL = '''{%- if main_doc -%}
{{ main_doc }}
{%- endif -%}

Usage:
    {{ name }} [options]

Options:
{%- for flg in flags %}
    {% if flg.shorthand -%}
        -{{ flg.shorthand }}, {% else %}{{ " " * 4 }}
    {%- endif -%}
    --{{ "%-*s %s"|format(opts_fmt_len, flg.name, flg.help or '')}}
    {%- if flg.default %} (default: {{flg.default}}){% endif -%}
{%- endfor %}
'''


class Command:
    def __init__(self, callback, **kwrgs):
        # note: docs are modified at runtime
        '''
        Args:
            callback: a function that runs the command

        Keyword Args:
            shorthands (dict): Give the command flags a shorthand use {<flag name>: <shorthand>},
                               has greater precedence over doc parsing.
            docs (dict): Give the command flags a doc string use {<flag name>: <help text>}
                         has greater precedence over doc parsing.
            defaults (dict): Give the command flags a default value use {<flag name>: <value>}
                             has greater precedence over doc parsing.
            hidden (set):  list of flags that should be hidden
            doc_help (bool): If True, use the callback __doc__ as the help text
                             for this command.
            help_template (str): template used for the help text
            check_names (bool): if True (True is default), the Command will check all the flag names given in
                                any command settings or function docs to see if they are valid flags.
        '''
        self.callback = callback
        if not callable(self.callback):
            raise Exception('Command callback needs to be callable')
        meta = self.callback.__code__
        self.flagnames = meta.co_varnames[:meta.co_argcount]

        self.shorthands = {}
        self.docs = {}

        self.name = self.callback.__name__
        self._help, flagdoc = parse_doc(self.callback.__doc__)
        for key, val in flagdoc.items():
            self.shorthands[key] = val.get('shorthand')
            self.docs[key] = val.get('doc')

        self.defaults = dict(
            zip(reversed(self.flagnames),
                reversed(self.callback.__defaults__ or []))
        )

        self.help_template = kwrgs.get('help_template') or HELP_TMPL
        self.hidden = kwrgs.get('hidden') or set()
        self.doc_help = kwrgs.get('doc_help') or False

        self.shorthands.update(kwrgs.get('shorthands') or {})
        self.docs.update(kwrgs.get('docs') or {})
        self.defaults.update(kwrgs.get('defaults') or {})

        self.flags = self._find_flags(flagdoc)

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

        self.parse_args(argv)

        fnargs = self._callback_args()
        return self.callback(**fnargs)


    def help(self):
        print(self.helptext())

    def helptext(self):
        helpflag = Option('help', bool, help='Get help.')
        helpflag.shorthand = 'h'

        flags = self.visible_flags()
        flags.append(helpflag)
        fmt_len = max([len(f) for f in flags])

        tmpl = jinja2.Template(self.help_template)
        return tmpl.render({
            'main_doc': self._help,
            'name': self.name,
            'opts_fmt_len': fmt_len,
            'flags': flags,
        })

    def _find_flags(self, flagdoc):
        if not self.flagnames:
            return dict() # there are no flags to find

        flags = {}
        for name in self.flagnames:
            opt = Option(
                name, self.callback.__annotations__.get(name),
                shorthand=self.shorthands.get(name),
                help=self.docs.get(name),
                value=self.defaults.get(name),
                hidden=True if name in self.hidden else False,
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
                raise Exception(f'{f} is not a flag')

    def _named_flags(self) -> dict:
        return {key: val for key, val in self.iter_named_flags()}

    def iter_named_flags(self):
        if not self.flags:
            return [] # so we dont iterate over None
        for name, flag in self.flags.items():
            if len(name) == 1 and flag.name in self.flags:
                continue
            yield name, flag

    def _callback_args(self) -> dict:
        return {name: f.value for name, f in self.iter_named_flags()}

    def visible_flags(self) -> list:
        return [f for _, f in self.iter_named_flags() if not f.hidden]

    def parse_args(self, args):
        args = args[:]
        while args:
            arg = args.pop(0)
            if '-' not in arg:
                self._cmd_args.append(arg)
                continue

            arg = arg.replace('-', '')
            val = None
            if '=' in arg:
                hasval = True
                arg, val = arg.split('=')

            if arg not in self.flags:
                raise Exception("could not find flag '{}'".format(arg))

            flag = self.flags[arg]

            if flag.type is bool:
                flag.value = True if flag.value is None else not flag.value
            elif val is not None:
                if flag.type is None.__class__:
                    flag.type = str
                flag.value = flag.type(val)
            elif args and args[0][0] != '-':
                flag.setval(args.pop(0))

    def run(self, argv=sys.argv):
        return self.__call__(argv)


class Option:
    def __init__(self, name, typ, *,
                 shorthand=None, help=None, value=None, hidden=None):
        self.name = name
        self.type = typ or bool
        self.shorthand = shorthand
        self.help = help
        self.value = value
        self.has_default = value is not None
        self.hidden = hidden if hidden is not None else False

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        if val is not None:
            self.type = val.__class__

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
        return "{}('{}--{}', {})".format(
            self.__class__.__name__,
            f'-{self.shorthand} ' if self.shorthand else '',
            self.name, self.type
        )

    def __str__(self):
        return '{}--{} {}'.format(
            f'-{self.shorthand} ' if self.shorthand else '',
            self.name, self.help)

    def __len__(self):
        '''Get the length of the option name when formatted in the help text
        eg. same as `len('-v, --verbose')`
        '''
        length = len(self.name) + 2 # plus len of '--'
        if self.shorthand:
            length += 4 # length of '-v, ' if v is the shorthand
        return length

def parse_doc(docstr):
    if docstr is None:
        return '', {}

    docparts = docstr.split('\n\n')
    if len(docparts) == 1:
        if ':' in docparts[0]:
            return '', _parse_flags_doc(docparts[0])
        else:
            return docstr.strip(), {}
    elif len(docparts) < 2:
        raise Exception('must have two new-lines (\\n\\n) separating command doc from flag docs')

    main_doc = '\n'.join([l.strip() for l in docparts[0].split('\n')])
    return main_doc, _parse_flags_doc(''.join(docparts[1:]))

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
    meta = fn.__code__
    flagnames = meta.co_varnames[:meta.co_argcount]
    maindoc, flagdoc = parse_doc(fn.__doc__)

    tmpl = jinja2.Template(HELP_TMPL)
    return tmpl.render({
        'main_doc': maindoc,
        'name': fn.__name__,
        'flags': Command(fn).visible_flags()
    })


def command(**kwrgs):
    def runner(fn):
        return Command(fn, **kwrgs)
    return runner


command.__doc__ = f'''
    Decrotator that creates a Command
{Command.__init__.__doc__}'''

Command.__init__.__doc__ = f'''
    Iinitialze a new Command
{Command.__init__.__doc__}'''