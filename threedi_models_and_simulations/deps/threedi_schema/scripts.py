import click
from threedi_schema import ThreediDatabase


@click.group()
@click.option(
    "-s",
    "--sqlite",
    type=click.Path(readable=True),
    help="Path to an sqlite (spatialite) file",
    required=True,
)
@click.pass_context
def main(ctx, sqlite):
    """Checks the threedi-model for errors / warnings / info messages"""
    ctx.ensure_object(dict)

    db = ThreediDatabase(sqlite, echo=False)
    ctx.obj["db"] = db


@main.command()
@click.option("-r", "--revision", default="head", help="The schema revision to migrate to")
@click.option("--backup/--no-backup", default=True)
@click.option("--set-views/--no-set-views", default=True)
@click.option("--upgrade-spatialite-version/--no-upgrade-spatialite-version", default=False)
@click.option("--convert-to-geopackage/--not-convert-to-geopackage", default=False)
@click.pass_context
def migrate(ctx, revision, backup, set_views, upgrade_spatialite_version, convert_to_geopackage):
    """Migrate the threedi model schematisation to the latest version."""
    schema = ctx.obj["db"].schema
    click.echo("The current schema revision is: %s" % schema.get_version())
    click.echo("Running alembic upgrade script...")
    schema.upgrade(
        revision=revision,
        backup=backup,
        upgrade_spatialite_version=upgrade_spatialite_version,
    )
    click.echo("The migrated schema revision is: %s" % schema.get_version())


@main.command()
@click.pass_context
def index(ctx):
    """Set the indexes of a threedi model schematisation."""
    schema = ctx.obj["db"].schema
    click.echo("Recovering indexes...")
    schema.set_spatial_indexes()
    click.echo("Done.")


if __name__ == "__main__":
    main()
