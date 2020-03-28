import sys
import jinja2
from .exceptions import UserException

from typing import Tuple, Any

HELP_TMPL = '''{%- if main_doc -%}
{{ main_doc }}

{% endif -%}
Usage:
    {{ usage }}
{%- if command_help %}

Commands:
{{ command_help }}
{%- endif %}

Options:
{%- for flg in flags %}
    {{ '{}'.format(flg) }}
{%- endfor%}
'''


class _CliBase:

    def __init__(self, **kwrgs):
        self.help_template = kwrgs.pop('help_template', HELP_TMPL)
        self.doc_help = kwrgs.pop('doc_help', False)

    def help(self, file=sys.stdout):
        print(self.helptext(), file=file)

    @staticmethod
    def process_arg(raw) -> Tuple[str, Any]:
        arg = raw.lstrip('-')
        arg, _, val = arg.partition('=')
        return arg.replace('-', '_'), val or None

    def helptext(self, template=None):
        if self.doc_help:
            return self._meta.doc

        flags = list(self.flags.visible_flags())
        fmt_len = self.flags.format_len
        for f in flags:
            f.f_len = fmt_len

        if hasattr(self, '_command_help'):
            command_help = self._command_help()
        else:
            command_help = None

        tmpl = jinja2.Template(template or self.help_template)
        return tmpl.render({
            'main_doc': self._help,
            'usage': self.usage,
            'flags': flags,
            'command_help': command_help,
        })

    def _setflag_from_args(self, args: list, arg: str, val: Any, flag):
        '''
        Do not use this.

        This function only exists to limit code reuse. There is no useful
        metaphore for understanding what this function does.

        It will set the value of a flag or find the value, otherwise it will
        throw an exception.
        '''
        if flag.type is not bool:
            # When the flag needs a value but there are no more arguments or
            # the next argument is a flag then we raise an error.
            if not val:
                if not args or args[0].startswith('-'):
                    raise UserException(f'no value given for --{flag.name}')
                val = args.pop(0)
            flag.setval(val)
        else:
            # catch the case where '=' has been used
            if val:
                raise UserException(f'cannot give {flag.name!r} flag a value')
            elif flag.has_default:
                flag.value = not flag._default
            else:
                flag.value = True