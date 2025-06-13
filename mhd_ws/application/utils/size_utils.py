import math

size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")


def get_size_in_str(size_in_bytes: int) -> str:
    if size_in_bytes == 0:
        return "0B"
    i = int(math.floor(math.log(size_in_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_in_bytes / p, 2)
    return "%s%s" % (s, size_names[i])
