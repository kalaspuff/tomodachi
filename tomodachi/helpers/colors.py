import os

NO_COLOR = any(
    [
        os.environ.get("NO_COLOR", "").lower() in ("1", "true"),
        os.environ.get("NOCOLOR", "").lower() in ("1", "true"),
        os.environ.get("TOMODACHI_NO_COLOR", "").lower() in ("1", "true"),
        os.environ.get("TOMODACHI_NOCOLOR", "").lower() in ("1", "true"),
        os.environ.get("CLICOLOR", "").lower() in ("0", "false"),
        os.environ.get("CLI_COLOR", "").lower() in ("0", "false"),
        os.environ.get("CLICOLOR_FORCE", "").lower() in ("0", "false"),
    ]
)


class ColorFore:
    BLACK = ""
    RED = ""
    GREEN = ""
    YELLOW = ""
    BLUE = ""
    MAGENTA = ""
    CYAN = ""
    WHITE = ""
    RESET = ""

    LIGHTBLACK_EX = ""
    LIGHTRED_EX = ""
    LIGHTGREEN_EX = ""
    LIGHTYELLOW_EX = ""
    LIGHTBLUE_EX = ""
    LIGHTMAGENTA_EX = ""
    LIGHTCYAN_EX = ""
    LIGHTWHITE_EX = ""


class ColorStyle:
    BRIGHT = ""
    DIM = ""
    NORMAL = ""
    RESET_ALL = ""


COLOR_0 = COLOR = ColorFore()
COLOR_STYLE_0 = COLOR_STYLE = ColorStyle()
COLOR_RESET_0 = COLOR_RESET = ""
try:
    import colorama  # noqa  # isort:skip

    if not NO_COLOR:
        COLOR = colorama.Fore
        COLOR_STYLE = colorama.Style
        COLOR_RESET = colorama.Style.RESET_ALL
except Exception:
    pass

__all__ = ["COLOR", "COLOR_STYLE", "COLOR_RESET", "COLOR_0", "COLOR_STYLE_0", "COLOR_RESET_0", "NO_COLOR"]
