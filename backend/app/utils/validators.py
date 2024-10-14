import re


def validate_setting_key(key):
    # Only allow alphanumeric characters and underscores, length between 3 and 50
    return bool(re.match(r"^[a-zA-Z0-9_]{3,50}$", key))


def validate_setting_value(value):
    # For now, just ensure it's a string and not too long
    return isinstance(value, str) and len(value) <= 255
