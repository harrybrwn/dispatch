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

import os.path
import sys
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
            doc_help (bool): If True, use the callback __doc__ as the help text
                             for this command.
            help_template (str): template used for the help text
            hidden (set):  list of flags that should be hidden
        '''
        self.help_template = kwrgs.get('help_template') or HELP_TMPL
        self.hidden = kwrgs.get('hidden') or set()
        self.doc_help = kwrgs.get('doc_help') or False

        self.defaults = kwrgs.get('defaults')
        self.shorthands = kwrgs.get('shorthands') or {}
        self.docs = kwrgs.get('docs') or {}

        self.callback = callback

        meta = self.callback.__code__
        self.flagnames = meta.co_varnames[:meta.co_argcount]
        self.name = self.callback.__name__
        self._help, flagdoc = parse_doc(self.callback.__doc__)
        self.flags = self._find_flags(flagdoc)
        self._cmd_args = []

        if self.shorthands:
            for s in self.shorthands:
                if s not in self.flagnames:
                    raise Exception(f'{s} is not a flag')

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

        defaults = {}
        for name, deflt in zip(reversed(self.flagnames), reversed(self.callback.__defaults__ or [])):
            defaults[name] = deflt

        if self.defaults:
            defaults.update(self.defaults)

        flags = {}
        for name in self.flagnames:
            opt = Option(name, self.callback.__annotations__.get(name))
            if name in self.docs:
                opt.help = self.docs[name]
            if name in self.shorthands:
                opt.shorthand = self.shorthands[name]
            if name in flagdoc:
                opt.shorthand = flagdoc[name]['short']
                opt.help = flagdoc[name]['doc']

            if name in defaults:
                opt.value = defaults[name]
            if opt.name in self.hidden:
                opt.hidden = True
            flags[name] = opt
            if opt.shorthand:
                flags[opt.shorthand] = opt

        return flags

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
                flag.value = flag.type(args.pop(0))

    def run(self, argv=sys.argv):
        if argv is sys.argv:
            argv = argv[1:]

        if '--help' in argv or '-h' in argv:
            return self.help()

        self.parse_args(argv)
        return self.callback(**self._callback_args())


class Option:
    def __init__(self, name, typ, *, help=None, value=None):
        self.name = name
        self.type = typ or bool
        self.shorthand = None
        self.help = help
        self._value = value
        self.has_default = value is not None
        self.hidden = False

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        self.type = val.__class__

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
    i = doc.index(':')
    s = doc[i:]

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
            res[names[1]] = {'doc': tmpdoc, 'short': names[0]}
        else:
            res[names[0]] = {'doc': tmpdoc, 'short': None}
    return res


def _find_opts(fn) -> list:
    meta = fn.__code__
    flagnames = meta.co_varnames[:meta.co_argcount]
    maindoc, flagdoc = parse_doc(fn.__doc__)
    flags = []

    for name in flagnames:
        opt = Option(name, fn.__annotations__.get(name))
        if name in flagdoc:
            opt.shorthand = flagdoc[name]['short']
            opt.help = flagdoc[name]['doc']
        flags.append(opt)
    return flags


def helptext(fn):
    meta = fn.__code__

    flagnames = meta.co_varnames[:meta.co_argcount]
    maindoc, flagdoc = parse_doc(fn.__doc__)

    tmpl = jinja2.Template(HELP_TMPL)
    return tmpl.render({
        'main_doc': maindoc,
        'name': fn.__name__,
        'flags': _find_opts(fn)
    })


def command(**kwrgs):
    def runner(fn):
        cmd = Command(fn, **kwrgs)
        return cmd.run
    return runner


command.__doc__ = f'''
    Decrotator that creates a Command
{Command.__init__.__doc__}'''

Command.__init__.__doc__ = f'''
    Iinitialze a new Command
{Command.__init__.__doc__}'''