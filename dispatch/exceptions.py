class UserException(Exception):
    pass


class RequiredFlagError(UserException):
    pass


class DeveloperException(Exception):
    pass


class BadFlagError(UserException):
    pass

class CommandNotFound(UserException):
    pass
