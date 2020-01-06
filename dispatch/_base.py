import sys
import jinja2

HELP_TMPL = '''{%- if main_doc -%}
{{ main_doc }}

{% endif -%}
Usage:
    {{ usage }}

Options:
{%- for flg in flags %}
    {{ '{}'.format(flg) }}
{%- endfor -%}

{% if command_help %}

Commands:
{{ command_help }}
{%- endif %}
'''


class _CliBase:

    def __init__(self, **kwrgs):
        self.help_template = kwrgs.pop('help_template', HELP_TMPL)
        self.doc_help = kwrgs.pop('doc_help', False)

    def help(self, file=sys.stdout):
        print(self.helptext(), file=file)

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
            'usage': self._usage,
            'flags': flags,
            'command_help': command_help,
        })