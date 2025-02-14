class MigrationMissingError(Exception):
    """Raised when 3Di model is missing migrations."""

    pass


class UpgradeFailedError(Exception):
    """Raised when an upgrade() fails"""
