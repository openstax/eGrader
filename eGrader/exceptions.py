class APIError(Exception):
    """This class allows application code to wrap exceptions so that they
       can be transformed into JSON using the flask exception handler
       hook.


      :var exception: Wrapped exception if any.
      :var message: Message provided by the caller.
      :var debug: Enable debug mode.  Result contains verbose error details.
      :var status_code: Status code provided by the caller. Default: 400.

    """
    status_code = 400

    def __init__(self, message, debug=False, status_code=None, exception=None):
        Exception.__init__(self)
        self.message = message
        self.debug = debug
        if status_code is not None:
            self.status_code = status_code
        self.exception = exception

    def to_dict(self):
        """Returns a dictionary of values that can be converted to json if
           needed.  In debug mode, the wrapped exception is also returned
           as a string.

        """
        result = dict(message=self.message, success=False)
        if self.debug and self.exception is not None:
            result['exception'] = str(self.exception)

    def __str__(self):
        return "API Error:" + ", Message: " + self.message + "\n" \
            + str(self.exception)


def api_error_handler(exception, debug=False):
    """The default error handler.  Wraps the exception in an API error object.

       :param exception: The exception to wrap.
       :param debug: Enable debug mode.  Result contains verbose error details.

    """
    return APIError('Unable to process this request',
                    exception=exception,
                    debug=debug)


class ResponsesNotFound(Exception):
    pass
