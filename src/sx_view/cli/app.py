import sys
from pathlib import Path
import traceback
from typing import Annotated
import yaml
from pydantic import BaseModel
import typer

from sx_view.cli import v

app = typer.Typer(no_args_is_help=True)

class Rasters(BaseModel):
    ids: list

class AppConfig(BaseModel):
    f_out_prefix: str
    wl_dir: Path
    f_aoi: Path
    rasters: Rasters
    odir: Path

def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)  # validation automatique

@app.command()
def main(
    input_yaml: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=True,
            help="Input yaml file containing parameters",
        ),
    ],
):
    # load configuration file
    conf = load_config(input_yaml)

    try:
        # output dir
        if not conf.odir.exists():
            conf.odir.mkdir(parents=True, exist_ok=True)

        # some check inputs
        if not conf.wl_dir.exists():
            raise typer.Exit("Waterline directory  does not exist")
        if not conf.f_aoi.exists():
            raise typer.Exit("File area of interest does not exist")

        # Run viewer
        v.viewer(conf)


    except Exception as e:  # noqa: BLE001
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED)
        typer.echo(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    app()
