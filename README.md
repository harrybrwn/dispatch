# dispatch

A low information-redundancy cli framework for a quick and dirty way of converting python scripts to a command line tool.

Inspired by [fire](https://github.com/google/python-fire) and [click](https://click.palletsprojects.com/).

```python
import dispatch

@dispatch.command()
def hello(verbose: bool=False, name: str='none', opt=None):
    '''Run the 'hello' command line interface.

    :v verbose: Run the command verbosly
    :n name: Name of the person you are saying hello to.
    :opt: Opt is just a generic option.
    '''
    print(f'hello, {name}')


if __name__ == '__main__':
    hello()
```