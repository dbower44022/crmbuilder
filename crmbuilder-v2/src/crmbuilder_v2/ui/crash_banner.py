"""Subprocess-died banner.

Wired in slice B. Per PRD section 4.3 / DEC-023, when the API
subprocess we own exits unexpectedly, a non-modal banner appears with
text "Storage server stopped." and a Reconnect button.
"""
