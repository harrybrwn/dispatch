class UserException(Exception):
    pass


class RequiredFlagError(UserException):
    pass


class DeveloperException(Exception):
    pass


class BadFlagError(UserException):
    pass