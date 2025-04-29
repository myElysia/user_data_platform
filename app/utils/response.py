from http import HTTPStatus


class ErrorResponse:
    status_means = dict({
        HTTPStatus.BAD_REQUEST: {"description": "Bad request"},
        HTTPStatus.NOT_FOUND: {"description": "Not found"},
        HTTPStatus.INTERNAL_SERVER_ERROR: {"description": "Server error"},
        HTTPStatus.BAD_GATEWAY: {"description": "Bad gateway"}
    })

    def __new__(cls, *args, **kwargs):
        """
        读取错误码并返回对应的错误提示，必须保证存在错误码
        :param args:
        :param kwargs:
        """
        return cls.status_means[args[0]]


class Response:
    def __init__(self, code, data=None):
        if code in ErrorResponse.status_means and not data:
            self.response = ErrorResponse(code)
        else:
            self.response = data

    def __call__(self, *args, **kwargs):
        return self.response
