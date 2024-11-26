from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("memos")
except PackageNotFoundError:
    __version__ = "Unknown"
