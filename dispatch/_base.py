import jinja2


class _BaseCommand:

    def __init__(self, **kwrgs):
        pass

    def help(self):
        print(self.helptext())

    def helptext(self):
        if self.doc_help:
            return self._meta.doc

        flags = list(self.flags.visible_flags())
        fmt_len = self.flags.format_len
        for f in flags:
            f.f_len = fmt_len

        if hasattr(self, '_command_help'):
            command_help = self._command_help
        else:
            command_help = None

        tmpl = jinja2.Template(self.help_template)
        return tmpl.render({
            'main_doc': self._help,
            'usage': self._usage,
            'flags': flags,
            'command_help': command_help,
        })