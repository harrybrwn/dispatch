# dispatch

A low information-redundancy cli framework for a quick and dirty way of converting python scripts to a command line tool.

Inspired by [fire](https://github.com/google/python-fire) and [click](https://click.palletsprojects.com/).

[docs.python]: # (cat example.py)
```python
# example.py
import dispatch

@dispatch.command(hidden={'debug'})
def hello(name: str, verbose: bool=False, debug=False):
    '''Run the 'hello' command line interface.

    :v verbose: Run the command verbosly
    :name: Name of the person you are saying hello to.
    '''
    if debug:
        print(f'debugging with {name}')
    else:
        print(f'hello, {name}')

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
        --name          Name of the person you are saying hello to.
    -v, --verbose       Run the command verbosly
    -h, --help          Get help.
```
