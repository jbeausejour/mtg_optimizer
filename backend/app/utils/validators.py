import re


def validate_setting_key(key):
    return bool(re.match(r"^[a-zA-Z0-9_]{3,50}$", key))


def validate_setting_value(value):
    return isinstance(value, str) and len(value) <= 255
