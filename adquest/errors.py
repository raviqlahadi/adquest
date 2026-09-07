"""Shared exception types for adquest."""


class QuestError(Exception):
    """User-facing error. Printed as a message by the CLI; exits with code 1.

    Carries the message exactly as it should be displayed (including any
    emoji/color wrapping applied at the raise site).
    """
