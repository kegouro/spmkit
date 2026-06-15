"""Interfaz de línea de comandos de spmkit.

Esta capa SOLO orquesta: parsea argumentos, llama al ``core`` y presenta
resultados. No contiene lógica de análisis.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from spmkit import __version__, load
from spmkit.core.analysis import kpfm, leveling, roughness
from spmkit.core.export import to_csv, to_json

app = typer.Typer(
    name="spmkit",
    help="Analizador open-source de datos AFM/KPFM (SPM Lab UTFSM).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"spmkit {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Muestra la versión y sale.",
    ),
) -> None:
    """spmkit: análisis de microscopía de sonda de barrido."""


@app.command()
def info(file: Path = typer.Argument(..., exists=True, help="Archivo .nid o .nhf")) -> None:
    """Muestra metadatos y canales del archivo."""
    data = load(file)
    table = Table(title=f"{file.name}  ·  formato {data.metadata.get('format', '?')}")
    table.add_column("Canal", style="cyan")
    table.add_column("Dirección")
    table.add_column("Forma")
    table.add_column("Unidad")
    table.add_column("Tamaño X·Y", justify="right")
    for ch in data.channels:
        table.add_row(
            ch.name,
            ch.direction,
            f"{ch.shape[0]}×{ch.shape[1]}",
            ch.unit,
            f"{ch.x_range * 1e6:.2f}×{ch.y_range * 1e6:.2f} µm",
        )
    console.print(table)


@app.command(name="roughness")
def roughness_cmd(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid o .nhf"),
    channel: str = typer.Option("Z-Axis", "--channel", "-c", help="Canal a analizar"),
    level: str = typer.Option("plane", "--level", "-l", help="Nivelación: plane|poly|none"),
) -> None:
    """Calcula parámetros de rugosidad (ISO 25178) de un canal."""
    data = load(file)
    ch = data[channel]
    ch = _apply_level(ch, level)
    result = roughness.statistics(ch)
    table = Table(title=f"Rugosidad · {channel} ({result.unit})")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    for key, value in result.to_dict().items():
        if isinstance(value, float):
            table.add_row(key, f"{value:.4g}")
        else:
            table.add_row(key, str(value))
    console.print(table)


@app.command()
def analyze(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid o .nhf"),
    output: Path = typer.Option(Path("./results"), "--output", "-o", help="Carpeta de salida"),
    channel: str = typer.Option("Z-Axis", "--channel", "-c"),
    cpd_channel: str = typer.Option("CPD", "--cpd-channel"),
    level: str = typer.Option("plane", "--level", "-l"),
    tip_work_function: float | None = typer.Option(
        None, "--tip-wf", help="Función de trabajo de la punta (eV) para KPFM"
    ),
) -> None:
    """Pipeline completo: rugosidad (+ KPFM si hay canal) → CSV + JSON."""
    data = load(file)
    output.mkdir(parents=True, exist_ok=True)
    stem = file.stem

    ch = _apply_level(data[channel], level)
    rough = roughness.statistics(ch)
    to_csv(rough, output / f"{stem}_roughness.csv")
    to_json(rough, output / f"{stem}_roughness.json")
    console.print(f"[green]✓[/] Rugosidad → {output / (stem + '_roughness.csv')}")

    if cpd_channel in data.names:
        cpd = kpfm.statistics(data[cpd_channel], tip_work_function=tip_work_function)
        to_csv(cpd, output / f"{stem}_kpfm.csv")
        to_json(cpd, output / f"{stem}_kpfm.json")
        console.print(f"[green]✓[/] KPFM → {output / (stem + '_kpfm.csv')}")
    else:
        console.print(f"[yellow]·[/] Sin canal CPD ({cpd_channel!r}); se omite KPFM.")


@app.command()
def gui() -> None:
    """Lanza la interfaz gráfica (requiere el extra 'gui')."""
    try:
        from spmkit.gui.app import run

        run()
    except ImportError:
        console.print("[red]La GUI requiere PyQt6. Instala con:[/] pip install 'spmkit[gui]'")
        raise typer.Exit(code=1) from None


def _apply_level(ch, level: str):  # type: ignore[no-untyped-def]
    if level == "plane":
        return leveling.plane_fit(ch)
    if level == "poly":
        return leveling.polynomial(ch, order=2)
    if level == "none":
        return ch
    raise typer.BadParameter("level debe ser plane|poly|none")


if __name__ == "__main__":
    app()
