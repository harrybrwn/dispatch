# dispatch

Dispatch a quick and dirty command line interface in python.

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