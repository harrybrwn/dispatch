import sys, os
import inspect
from types import FunctionType, MethodType

from .flags import FlagSet
from ._meta import _FunctionMeta, _GroupMeta, _isgroup
from ._base import _CliBase
from .exceptions import (
    UserException, DeveloperException,
    RequiredFlagError, BadFlagError
)

from typing import Optional, List, Generator, Callable, Any


class Command(_CliBase):

    def __init__(self, callback: Callable, **kwrgs):
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
        '''
        super().__init__(**kwrgs)

        self.callback = callback
        if not callable(self.callback):
            raise DeveloperException('Command callback needs to be callable')

        self._meta = _FunctionMeta(
            self.callback,
            instance=kwrgs.pop('__instance__', None)
        )
        self._help = self._meta.helpstr
        self._usage = kwrgs.pop('usage', f'{self._meta.name} [options]')
        self._help = kwrgs.pop('help', self._help)

        self.args: List[str] = []
        self.flags = FlagSet(
            names=self._meta.params(),
            __command_meta__=self._meta,
            **kwrgs,
        )

    @property
    def usage(self):
        return self._usage

    @property
    def name(self):
        return self._meta.name

    @name.setter
    def name(self, newname):
        self._meta.name = newname

    def __call__(self, argv=sys.argv):
        if argv is sys.argv:
            argv = argv[1:]
        if '--help' in argv or 'help' in argv or '-h' in argv:
            return self.help()

        fn_args = self.parse_args(argv)

        if self._meta.has_variadic_param():
            res = self._meta.run(*self.args, **fn_args)
        else:
            res = self._meta.run(**fn_args)

        if res is not None:
            print(res)
        return res

    def __repr__(self):
        return f'{self.__class__.__name__}({self._meta.name}{self._meta.signature})'

    def __str__(self):
        return self.helptext()

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
                    raise UserException(f'cannot give {flag.name!r} flag a value')
                elif flag.has_default:
                    flag.value = not flag._default
                else:
                    flag.value = True if flag.value is None else flag.value
        return {n: f.value for n, f in self.flags.items()}

    def run(self, argv=sys.argv):
        return self.__call__(argv)

def _find_commands(obj) -> Generator[tuple, None, None]:
    for name, attr in obj.__dict__.items():
        ok = (
            not name.startswith('_') and
            isinstance(attr, (
                FunctionType,
                MethodType,
                _CliBase,
            ))
        )
        if ok:
            yield name, attr

def _retrieve_commands(obj):
    cmds = {}
    seen = set()
    aliases = {}
    for name, attr in obj.__dict__.items():
        ok = (
            not name.startswith('_') and
            isinstance(attr, (
                FunctionType,
                MethodType,
                _CliBase,
            ))
        )
        if ok:
            if attr in seen:
                # aliases[name] = attr.__name__
                if isinstance(attr, _CliBase):
                    aliases[attr.name] = name
                else:
                    aliases[attr.__name__] = name
            else:
                seen.add(attr)
                cmds[name] = attr
    return cmds, aliases


class SubCommand(Command):
    '''
    SubCommands are meant to be added to a command group with the 'subcommand'
    decorator. This is a way to specify extra features for a command and
    is NOT NECCESARY for the creation of an actual subcommand. Adding the
    'subcommand' decorator to all of the subcommands will hinder preformance
    slightly.

    The second purpose of this class is for Group's internal sub-command use.
    '''

    def __init__(self, callback, hidden=False, **kwrgs):
        self.group = kwrgs.pop('__command_group__', None)
        super().__init__(callback, **kwrgs)
        self.hidden = hidden

    @property
    def usage(self):
        if self.group is None:
            return self._usage
        return f'{self.group.name} {self._meta.name} [options]'


class Group(_CliBase):
    def __init__(self, obj, **kwrgs):
        '''
        Args:
            obj: a class that will be used as the command groups

        Keyword args:
            usage:
            help_template:
            doc_help:
            help:
        '''
        super().__init__(**kwrgs)
        self._usage = kwrgs.pop('usage', None)

        if isinstance(obj, type):
            init = kwrgs.pop('init', dict())
            self.inst = obj(**init) # TODO: find a way to make this safer
            self.type = obj
        else:
            ...
            self.inst = obj
            self.type = obj.__class__

        self.args = []
        self.name = self.type.__name__

        # self.commands = dict(_find_commands(self.type))
        self.commands, self.aliases = _retrieve_commands(self.type)

        self._hidden = kwrgs.pop('hidden', set())
        for c in self.commands.values():
            if isinstance(c, SubCommand) and c.hidden:
                self._hidden.add(c.name)

        self._meta = _GroupMeta(self.inst)
        self._help = kwrgs.pop('help', self._meta.helpstr)
        self.flags = FlagSet(
            names=tuple(self._meta.flagnames()),
            __command_meta__=self._meta,
            hidden=self._hidden,
            **kwrgs,
        )

        def new_getattr(this, name):
            if name in self.flags:
                flag = self.flags[name]
                return flag.value or flag._getnull()
            else:
                return object.__getattribute__(this, name)

        def new_setattr(this, name: str, val):
            if name in self.flags:
                flag = self.flags[name]
                if not isinstance(val, flag.type):
                    val = flag.type(val)
                flag._value = val
            object.__setattr__(this, name, val)

        self.type.__getattr__ = new_getattr
        self.type.__setattr__ = new_setattr

    @property
    def usage(self):
        return self._usage or f'{self.name} [options] [command]'

    def __call__(self, argv: List[str] = sys.argv):
        if argv is sys.argv:
            argv = argv[1:]
        if argv:
            if 'help' in argv[0]:
                if argv[1:] and self.iscommand(argv[1]):
                    return self._get_command(argv[1]).help()
                else:
                    return self.help()
            elif argv[0] == '-h':
                return self.help()

        cmd = self.parse_args(argv)

        # if the command is callable and no arguments are given,
        # we dont want to trigger the help message.
        if callable(self.inst):
            self.inst()
            if cmd is None:
                return
        elif cmd is None:
            self.help()
            sys.exit(1)

        return cmd(self.args)

    def _reset(self):
        self.args = []
        for f in self.flags.values():
            setattr(self.inst, f.name, f._getnull())

    def iscommand(self, name: str) -> bool:
        name = name.replace('-', '_')
        return (
            not name.startswith('_') and
            name in self.commands
        )

    def _get_command(self, name: str) -> SubCommand:
        fn = self.commands[name.replace('-', '_')]

        if isinstance(fn, SubCommand):
            fn._meta.set_instance(self.inst)
            fn.group = self
            return fn
        return SubCommand(fn, __instance__=self.inst, __command_group__=self)

    def parse_args(self, args: List[str]) -> Optional[SubCommand]:
        # TODO: use the Flag.setval in addition to this method of saving
        # the variable.
        nextcmd = None
        while args:
            # Need to find either a command or a flag
            # otherwise, add an argument an move on.
            raw_arg = args.pop(0)
            # we only want to find the first command it the args
            if nextcmd is None and self.iscommand(raw_arg):
                nextcmd = self._get_command(raw_arg)
                continue

            if raw_arg[0] != '-':
                self.args.append(raw_arg)
                continue

            arg = raw_arg.lstrip('-').replace('-', '_')
            val: Any = None
            if '=' in arg:
                arg, val = arg.split('=')

            flag = self.flags.get(arg)
            if flag is None:
                if nextcmd is None:
                    # if we have not found a sub-command yet then the unkown
                    # flag should not be passed on to any other commands we
                    # should throw and error for an unknown flag
                    raise BadFlagError(f'{arg!r} is not a flag')
                # if the flag is not in the group, then it might be
                # for the next command (self.args is passed the the next
                # command).
                self.args.append(raw_arg)
                if val is not None:
                    self.args.append(val)
                continue
            elif flag.type is not bool:
                if val is None:
                    if not args or args[0].startswith('-'):
                        raise UserException(f'{raw_arg!r} must be given a value.')
                    val = args.pop(0)
            else:
                # catch the case where '=' has been used
                if val is not None:
                    raise UserException(f'{raw_arg!r} should not be given a value.')
                val = True
            setattr(self.inst, arg, val)
        return nextcmd

    # TODO: hidden sub-commands should go here
    # make a Sub-Command class that has a hidden attibute to make this cleaner
    def _command_help(self) -> Optional[str]:
        docs = []
        keys = []
        for k in self.commands.keys():
            if k in self._hidden:
                continue
            if k in self.aliases:
                k += f', {self.aliases[k]}'
            keys.append(k)

        try:
            l = max(len(k) for k in keys)
        except ValueError:
            # max fails if there are no commands
            return None

        fmt = '\n'.join(
            f'    {k:<{l}}   {"{}"}'
            for k in keys
        )

        for name, c in self.commands.items():
            if name in self._hidden:
                continue
            if isinstance(c, SubCommand):
                docs.append(c._meta.helpstr)
            elif c.__doc__:
                for line in c.__doc__.split('\n'):
                    if line:
                        docs.append(line.strip())
                        break
            else:
                docs.append('')
        return fmt.format(*docs)


def helptext(fn) -> str:
    return Command(fn).helptext()


def command(_obj=None, **kwrgs):
    '''A decorator for creating commands

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
    '''
    def cmd(obj):
        if _isgroup(obj):
            return Group(obj, **kwrgs)
        return Command(obj, **kwrgs)

    # command is being called with parens as @command(...)
    if _obj is None:
        return cmd
    # being called without parens as @command
    return cmd(_obj)


def subcommand(_obj=None, **kwrgs):
    '''A decorator for sub-commands of a command group

    Keyword Args:
        hidden `bool`: will hide the entire command if set to True
    '''
    def subcmd(obj):
        return SubCommand(obj, **kwrgs)

    if _obj is None:
        return subcmd

    return subcmd(_obj)


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
