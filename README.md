# dispatch

A low information-redundancy cli framework for a quick and dirty way of converting python scripts to a command line tool.

Inspired by [fire](https://github.com/google/python-fire) and [click](https://click.palletsprojects.com/).

## Install
```
pip install py-dispatch
```

## Demo
[docs.python]: # (cat example.py)
```python
# example.py
import dispatch
import sys

@dispatch.command
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
