"""Read-only console API (batch4.md section 36).

Build and ask never import this package. It may import both.
"""

from governor.integrations.console.router import make_console_router, mount_console

__all__ = ["make_console_router", "mount_console"]
