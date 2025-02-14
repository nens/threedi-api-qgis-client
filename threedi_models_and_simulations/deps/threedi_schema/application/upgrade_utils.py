import logging
from typing import Callable, TYPE_CHECKING

from alembic.config import Config
from alembic.script import ScriptDirectory

if TYPE_CHECKING:
    from .schema import ModelSchema
else:
    ModelSchema = None


class ProgressHandler(logging.Handler):
    def __init__(self, progress_func, total_steps):
        super().__init__()
        self.progress_func = progress_func
        self.total_steps = total_steps
        self.current_step = 0

    def emit(self, record):
        msg = record.getMessage()
        if msg.startswith("Running upgrade"):
            self.progress_func(100 * self.current_step / self.total_steps)
            self.current_step += 1


def get_upgrade_steps_count(
    config: Config, current_revision: int, target_revision: str = "head"
) -> int:
    """
    Count number of upgrade steps for a schematisation upgrade.

    Args:
        config: Config parameter containing the configuration information
        current_revision: current revision as integer
        target_revision: target revision as zero-padded 4 digit string or "head"
    """
    if target_revision != "head":
        try:
            int(target_revision)
        except TypeError:
            # this should lead to issues in the upgrade pipeline, lets not take over that error handling here
            return 0
    # walk_revisions also includes the revision from current_revision to previous
    # reduce the number of steps with 1
    offset = -1
    # The first defined revision is 200; revision numbers < 200 will cause walk_revisions to fail
    if current_revision < 200:
        current_revision = 200
        # set offset to 0 because previous to current is not included in walk_revisions
        offset = 0
    if target_revision != "head" and int(target_revision) < current_revision:
        # assume that this will be correctly handled by alembic
        return 0
    current_revision_str = f"{current_revision:04d}"
    script = ScriptDirectory.from_config(config)
    # Determine upgrade steps
    revisions = script.walk_revisions(current_revision_str, target_revision)
    return len(list(revisions)) + offset


def setup_logging(
    schema: ModelSchema,
    target_revision: str,
    config: Config,
    progress_func: Callable[[float], None],
):
    """
    Set up logging for schematisation upgrade

    Args:
        schema: ModelSchema object representing the current schema of the application
        target_revision: A str specifying the target revision for migration
        config: Config object containing configuration settings
        progress_func: A Callable with a single argument of type float, used to track progress during migration
    """
    n_steps = get_upgrade_steps_count(config, schema.get_version(), target_revision)
    logger = logging.getLogger("alembic.runtime.migration")
    logger.setLevel(logging.INFO)
    handler = ProgressHandler(progress_func, total_steps=n_steps)
    logger.addHandler(handler)
