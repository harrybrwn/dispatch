# dispatch

A low information-redundancy cli framework for a quick and dirty way of converting python scripts to a command line tool.

Inspired by [fire](https://github.com/google/python-fire) and [click](https://click.palletsprojects.com/).

## Install
```
pip install py-dispatch
```

## Demo
[docs.python]: # (grep -Pzo "[[?s]]# example\.py.*[[?=#end example\.py]]" example.py | tr -d '\0')
```python
# example.py
import sys
from dispatch import command

@command
def hello(name: str, verbose: bool, debug: bool, file: str = 'stdout'):
    '''Run the 'hello' command line interface.

    :v verbose: Run the command verbosly
    :name: Name of the person you are saying hello to.
    :file: Either stdout or stderr
    '''
    if debug:
        print(f'debugging with {name}', file=getattr(sys, file))
    else:
        print(f'hello, {name}', file=getattr(sys, file))

if __name__ == '__main__':
    hello()
```

```
$ python example.py --help
```

[docs]: # (python example.py --help)
```
Run the 'hello' command line interface.

Usage:
    hello [options]

Options:
        --name      Name of the person you are saying hello to.
    -v, --verbose   Run the command verbosly
        --debug
        --file      Either stdout or stderr (default: stdout)
    -h, --help      Get help.
```

Arguments
---------
Arguments can be retrieved in two ways, either from Command.args or with positional only arguments. When a cli function is run, it is replaced with a Command object so the cli function can use the command in it's own body.
```python
@dispatch.command
def cli(verbose: bool):
    print(cli.args)
```
Running this cli with `python cli.py hello --verbose these are some args` will result in `['hello', 'these', 'are', 'some', 'args']`.

The Other way to get arguments is to give the cli function a positional only argument at the beginning of the parameters list.
```python
@dispatch.command
def cli(*args, verbose: bool):
    print(args)
```
Running this cli as before will have the same result. However, it only works when the args tuple is the first function parameter.

Properties of Flags
===================
Because flags are specified by function arguments, the properties of flags are a little bit weird.

Boolean Flags
-------------
All boolean flags have a default of `False`.

A positional argument with no default and no type annotation is assumed to be a boolean flag and will default to a value of `False`.
```python
@disptch.command
def cli(verbose):
    if verbose:
        print('the verbose flag has been given')
    else:
        print('using default of False for verbose')
```

Flag Types
----------
Dispatch uses type annotations to infer flag types and will use those annotations to convert the arguments given.
```python
# cli.py
@dispatch.command
def cli(num: complex, decimal: float):
    pass
```
When the program `cli.py` is executed it will convert each argument to its type.
```bash
python cli.py --num=5+3j --decimal=5.9
```
For this command, the parser internals will eventually call `complex('5+3j')` and `float('5.9')` before giving the values as function arguments.
What this means is that you can use any type as long it has an `__init__` function that takes one argument. However there are exceptions

Multiple Commands
=================
For more complicated command line interfaces, you need more than just flags. To do this you simply use the same `command` decorator on a class instead of a function.

[docs.python]: # (cat multicommand.py)
```python
# multicommand.py
from dispatch import command

@command
class multicommand:
    verbose: bool = False

    def cat(self, file: str):
        '''Print a file

        :f file: print this file'''
        if self.verbose:
            print('doing the thing verbosly')
        print(open(file, 'r').read())

    def do(self, thing):
        '''Do a thing'''
        print('doing', thing)

if __name__ == "__main__":
    multicommand()
```

This small program is used just like any other cli.
```bash
python multicommand.py --help
```

[docs]: # (python multicommand.py --help)
```
Usage:
    multicommand [options] [command]

Options:
        --verbose    (default: False)
    -h, --help      Get help.

Commands:
    cat Print a file
    do  Do a thing
```
