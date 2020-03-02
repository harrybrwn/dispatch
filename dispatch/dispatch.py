import sys, os
import inspect
from types import FunctionType, MethodType

from .flags import FlagSet
from ._meta import _FunctionMeta, _GroupMeta, _isgroup
from ._base import _CliBase
from .exceptions import (
    UserException, DeveloperException,
    RequiredFlagError, BadFlagError,
    CommandNotFound,
)

from typing import Optional, List, Generator, Callable, Any


class Command(_CliBase):

    def __init__(self, callback: Callable, **kwrgs):
        # note: docs are modified at runtime
        '''
        Initialze a new Command

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
            instance=kwrgs.pop('__instance__', None) # for commands that are part of a group
        )
        self._usage = kwrgs.pop('usage', f'{self._meta.name} [options]')
        self._help = kwrgs.pop('help', self._meta.helpstr)

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

        if isinstance(res, int):
            # sys.exit(res)
            ...
        elif res and isinstance(res, str):
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

            arg, val = _CliBase.process_arg(arg)
            flag = self.flags.get(arg)

            if not flag:
                raise UserException(f'could not find flag {arg!r}')

            self._setflag_from_args(args, arg, val, flag)
        return {n: f.value for n, f in self.flags.items()}

    def run(self, argv=sys.argv):
        return self.__call__(argv)

def _retrieve_commands(obj):
    cmds = {}
    seen = set()
    aliases = {}
    for name, attr in obj.__dict__.items():
        ok = (
            not name.startswith('_') and
            isinstance(attr, (
                staticmethod,
                FunctionType,
                MethodType,
                _CliBase,
            ))
        )
        if ok:
            if attr in seen:
                if isinstance(attr, _CliBase):
                    aliases[attr.name] = name
                elif isinstance(attr, staticmethod):
                    aliases[attr.__func__.__name__] = name
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
        if isinstance(callback, staticmethod):
            callback = callback.__func__
            kwrgs.pop('__instance__')  # static methods do not need an instance

        self.group = kwrgs.pop('__command_group__', None)
        super().__init__(callback, **kwrgs)
        self.hidden = hidden

    @property
    def usage(self):
        if self.group is None:
            return self._usage
        elif self._usage.startswith(self.group.name):
            return self._usage
        else:
            return f'{self.group.name} {self._usage}'


class Group(_CliBase):
    def __init__(self, obj, **kwrgs):
        '''
        Args:
            obj: a class that will be used as the command groups

        Keyword args:
            usage: A string displayed in the usage part of the help message.
            hidden: A set of names of commands or flags that should be hidden.
            init: A dictionary that will be passes to the classes init function.
            help_template: Give a custom template for the help message.
            help: Give a custom description for the help message.
            silent: 'True' to stop the help message from printing when no arguments are given.
            doc_help:
        '''
        super().__init__(**kwrgs)
        self._usage = kwrgs.pop('usage', None)
        self.silent = kwrgs.pop('silent', False)
        self.init = kwrgs.pop('init', dict())

        if isinstance(obj, type):
            self.inst = None
            self.type = obj
        else:
            self.inst = obj
            self.type = obj.__class__

        self.args = []
        self.name = self.type.__name__

        self.commands, self.aliases = _retrieve_commands(self.type)
        for k, alias in self.aliases.items():
            self.commands[alias] = self.commands[k]

        self._hidden = kwrgs.pop('hidden', set())
        for c in self.commands.values():
            if isinstance(c, SubCommand) and c.hidden:
                self._hidden.add(c.name)

        self._meta = _GroupMeta(self.type)
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

        # This is a no-op but I left it here for future shenanigans
        def new_new(this, *args, **kwrgs):
            return super(self.type, this).__new__(this)

        self.type.__new__ = new_new
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

        try:
            self.inst = self.type(**self.init)
        except TypeError:
            raise TypeError(
                f"""can't call __init__ for a {self.type.__name__},
        try passing the 'init' dict as an argument to @command.""")

        cmd, cur_flags = self.parse_args(argv)
        for name, val in cur_flags.items():
            setattr(self.inst, name, val)

        if callable(self.inst) and cmd is None:
            ret = self.inst()
        elif cmd is None:
            if not self.silent:
                self.help()
            ret = None  # my tests monkey patch the exit function
            sys.exit(1)
        else:
            ret = cmd(argv=self.args)

        if isinstance(ret, int):
            sys.exit(ret)
        else:
            return ret

    # this is only really used while testing
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

    def parse_args(self, args: List[str]):  # -> Optional[SubCommand]:
        # TODO: add support for multiple flag shorthands (-vxcf instead of -v -x -c -f)
        nextcmd = None
        flags = {}
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

            arg, val = _CliBase.process_arg(raw_arg)
            flag = self.flags.get(arg)

            if flag is None:
                if nextcmd is None:
                    # if we have not found a sub-command yet then the unkown
                    # flag should not be passed on to any other commands we
                    # should throw and error for an unknown flag
                    if self.args:
                        raise CommandNotFound(f'{self.args[0]!r} is not a command')
                    else:
                        raise BadFlagError(f'{raw_arg!r} is not a flag')

                # if the flag is not in the group, then it might be
                # for the next command (self.args is eventually passed
                # to the next command).
                self.args.append(raw_arg)
                continue

            self._setflag_from_args(args, arg, val, flag)
            flags[flag.name] = flag.value
            # setattr(self.inst, flag.name, flag.value)
        return nextcmd, flags

    # TODO: this is a totol mess, please, someone fix this.
    def _command_help(self) -> Optional[str]:
        '''
        returns the command part of the help text as a string.
        '''
        docs = []
        keys = []

        cmds = {k: v for k, v in self.commands.items()}
        for alias in self.aliases.values():
            cmds.pop(alias)
        for k in cmds.keys():
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
    '''A decorator for creating cli commands

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