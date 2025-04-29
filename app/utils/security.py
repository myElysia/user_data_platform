import re


def validate_password(password: str):
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    elif not re.search(r'[A-Z]', password):
        raise ValueError('密码中缺少大写字符')
    elif not re.search(r'[a-z]', password):
        raise ValueError('密码中缺少小写字符')
    elif not re.search(r'[0-9]', password):
        raise ValueError('密码中缺少数字')
    elif not re.search(r'[!@#$%^&*_]', password):
        raise ValueError('密码中应该包含特殊字符')
