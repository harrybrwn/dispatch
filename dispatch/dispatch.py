import sys
import jinja2

from .flags import FlagSet
from ._meta import _FunctionMeta, _GroupMeta, _isgroup
from .exceptions import UserException, DeveloperException, RequiredFlagError
import inspect
from types import FunctionType, MethodType


HELP_TMPL = '''{%- if main_doc -%}
{{ main_doc }}

{% endif -%}
Usage:
    {{ usage }}

Options:
{%- for flg in flags %}
    {{ '{}'.format(flg) }}
    {%- if flg.has_default %} {{ flg.show_default() }}{% endif %}
{%- endfor %}
'''


class Command:

    def __init__(self, callback, **kwrgs):
        # note: docs are modified at runtime
        '''
        Args:
            callback: a function that runs the command

        Keyword Args:
            usage (str): Give the command a custom usage line.
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
            allow_null (bool):  If True (default is True), flags are allowed to be null
        '''
        self.callback = callback
        if not callable(self.callback):
            raise DeveloperException('Command callback needs to be callable')

        self._meta = _FunctionMeta(
            self.callback,
            instance=kwrgs.get('__instance__')
        )
        self.flagnames = self._meta.params()
        self._help = self._meta.helpstr
        self._usage = kwrgs.get('usage', f'{self._meta.name} [options]')

        self._help = kwrgs.get('help', self._help)
        self.help_template = kwrgs.get('help_template', HELP_TMPL)
        self.doc_help = kwrgs.get('doc_help', False)
        self.allow_null = kwrgs.get('allow_null', True)

        self.args = []
        self.flags = FlagSet(
            names=self._meta.params(),
            __funcmeta__=self._meta,
            **kwrgs,
        )

    def __call__(self, argv=sys.argv):
        if argv is sys.argv:
            argv = argv[1:]
        if '--help' in argv or 'help' in argv or '-h' in argv:
            return self.help()

        fn_args = self.parse_args(argv)

        if self._meta.has_variadic_param():
            return self._meta.run(*self.args, **fn_args)
        return self._meta.run(**fn_args)

    def __repr__(self):
        return f'{self.__class__.__name__}({self._meta.name}{self._meta.signature})'

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
            'usage': self._usage,
            'flags': flags,
        })

    def parse_args(self, args: list) -> dict:
        '''
        Parse a list of strings and return a dictionary of function arguments.
        The return values is supposd to be unpacked and used as an argument
        to the Command's callback function.
        '''
        self.args = []
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

            flag = self.flags.get(arg)

            if not flag:
                raise UserException(f'could not find flag {arg!r}')

            if flag.type is not bool:
                if not val:
                    if args and args[0][0] != '-':
                        # if the next arg is not a flag then it is the flag val
                        # but only if it is not for a boolean flag
                        val = args.pop(0)
                    else:
                        raise UserException(
                            f'no value given for --{flag.name}')
                flag.setval(val)
            else:
                if val:
                    raise UserException('cannot give boolean flag a value')
                elif flag.has_default:
                    flag.value = not flag._default
                else:
                    flag.value = True if flag.value is None else flag.value

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


def _find_commands(obj):
    for name, attr in obj.__dict__.items():
        ok = (
            not name.startswith('_') and
            isinstance(attr, (
                FunctionType,
                MethodType
            ))
        )
        if ok:
            yield name, attr


class Group:
    def __init__(self, obj, *args, **kwrgs):
        if isinstance(obj, type):
            self.inst = obj(*args, **kwrgs)
            self.type = obj
        else:
            self.inst = obj
            self.type = obj.__class__

        self.args = []
        self.doc = self.inst.__doc__
        self.commands = dict(_find_commands(self.type))

    def __call__(self, *args, argv=sys.argv, **kwrgs):
        if argv is sys.argv:
            argv = argv[1:]
        cmd, flags = self.parse_args(argv)

        if callable(self.inst):
            self.inst(*args, **kwrgs)

    def _get_command(self, name):
        # cannot use 'private' function or dunder methods as commands
        if name.startswith('_'):
            return None
        fn = self.type.__dict__.get(name)

        if fn is None:
            return None
        elif isinstance(fn, Command):
            fn._meta.add_instance(self.inst)
            return fn
        return Command(fn, __instance__=self.inst)

    def parse_args(self, args: list) -> tuple:
        args = args[:]
        nextcmd = None
        flags = {}
        while args:
            arg = args.pop(0)
            # Need to find either a command or a flag
            # otherwise, add an argument an move on.
            cmd = self._get_command(arg)
            if cmd:
                nextcmd = cmd
            elif arg[0] != '-':
                self.args.append(arg)
                continue
        return nextcmd, flags


def helptext(fn):
    return Command(fn).helptext()


def command(_obj=None, *args, **kwrgs):
    def cmd(obj):
        if _isgroup(obj):
            return Group(obj, *args, **kwrgs)
        return Command(obj, **kwrgs)

    # command is being called with parens as @command(...)
    if _obj is None:
        return cmd
    # being called without parens as @command
    return cmd(_obj)


def handle(fn):
    try:
        fn()
    except UserException as e:
        print('Error:', e, file=sys.stderr)
        return 1
    return 0


command.__doc__ = f'''
    Decrotator that creates a Command
{Command.__init__.__doc__}'''

Command.__init__.__doc__ = f'''
    Initialze a new Command
{Command.__init__.__doc__}'''
