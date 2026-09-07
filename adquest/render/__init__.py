"""Output rendering: format globals, low-level helpers, renderer selection.

FORMAT/VERBOSE are module-level globals set once by the CLI. Functions in
this package read them at call time; other modules must set them via
attribute assignment (``render.FORMAT = ...``).
"""
import sys

FORMAT = "ansi"  # global, set by cli --format flag
VERBOSE = False  # global, set by cli --verbose flag

# --- Colors ---
C_RESET = "\033[0m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"


def colored(text: str, color: str) -> str:
    """Wrap text in ANSI color codes. Returns plain text in chat format."""
    if FORMAT == "chat":
        return text
    return f"{color}{text}{C_RESET}"


def bar(current: int, maximum: int, width: int = 20) -> str:
    """Render a progress bar with filled/empty blocks."""
    if FORMAT == "chat":
        return f"{current}/{maximum}"
    filled = int(current / maximum * width) if maximum else 0
    return f"{colored('█' * filled, C_GREEN)}{colored('░' * (width - filled), C_DIM)}"


def vprint(msg: str) -> None:
    """Print a message only when verbose mode is active."""
    if VERBOSE:
        print(colored(f"  [debug] {msg}", C_DIM))


def streak_emoji(state: dict) -> str:
    """Fire emojis scaled by streak length, snowflake when cold."""
    return "🔥" * min(state["streak"], 5) if state["streak"] > 0 else "❄️"


def xp_display(state: dict) -> str:
    """Format the XP counter, handling the max-level (no next) case."""
    return f"{state['xp']}/{state['xp_next']}" if state["xp_next"] else f"{state['xp']}/∞"


def get_renderer():
    """Return the renderer matching the active output format."""
    from .ansi import AnsiRenderer
    from .chat import ChatRenderer

    if FORMAT == "chat":
        return ChatRenderer()
    return AnsiRenderer()


def eprint_stderr_unexpected_error(err: Exception) -> None:
    """Print the catch-all unexpected-error line (kept verbatim from v1)."""
    print(f"\n\033[31m❌ Unexpected error: {err}\033[0m", file=sys.stderr)
