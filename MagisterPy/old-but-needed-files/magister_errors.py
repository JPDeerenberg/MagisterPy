class BaseMagisterError(Exception):
    def __init__(self, message=None):
        super().__init__(message)
        self.message = message

class UnableToInputCredentials(BaseMagisterError):
    def __init__(self, message="\nCouldn't input credentials (Order: School->User->Pass)"):
        super().__init__(message)

class IncorrectCredentials(BaseMagisterError):
    def __init__(self, message="\nIncorrect credentials or Magister rejected them"):
        super().__init__(message)

class ConnectionError(BaseMagisterError):
    def __init__(self, message="\nCould not connect to Magister."):
        super().__init__(message)

class NotLoggedInError(BaseException):
    def __init__(self, message="You were not logged in before running this function"):
        super().__init__(message)

class AuthcodeError(BaseMagisterError):
    def __init__(self, message="\nCould not get authcode from javascript."):
        super().__init__(message)

class FetchError(BaseMagisterError):
    def __init__(self, message="\nError fetching data."):
        super().__init__(message)