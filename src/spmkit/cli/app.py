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
def nanomech(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid con espectroscopía"),
    channel: str = typer.Option("Deflection", "--channel", "-c", help="Canal de fuerza (N)"),
    curve: int = typer.Option(-1, "--curve", help="Índice de curva (-1 = la del medio)"),
    tip_radius: float = typer.Option(10e-9, "--tip-radius", help="Radio de punta (m)"),
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone"),
) -> None:
    """Ajusta una curva fuerza-distancia (Hertz) y estima el módulo de Young."""
    from spmkit.core.analysis import mechanics

    data = load(file)
    ch = data[channel]
    curves = mechanics.extract_curves(ch)
    if not curves:
        console.print("[red]No se encontraron curvas en el canal.[/]")
        raise typer.Exit(1)
    idx = len(curves) // 2 if curve < 0 else curve
    result = mechanics.fit_hertz(curves[idx], tip_radius=tip_radius, model=model)
    table = Table(title=f"Nanomecánica · curva {idx}/{len(curves)} · {model}")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("Módulo de Young", f"{result.young_modulus / 1e6:.4g} MPa")
    table.add_row("Punto de contacto", f"{result.contact_point * 1e9:.2f} nm")
    table.add_row("Adhesión", f"{result.adhesion * 1e9:.3g} nN")
    table.add_row("RMSE", f"{result.rmse:.3e}")
    console.print(table)


@app.command()
def batch(
    folder: Path = typer.Argument(..., exists=True, file_okay=False, help="Carpeta con archivos"),
    channel: str = typer.Option("Z-Axis", "--channel", "-c"),
    output: Path = typer.Option(Path("batch_summary.csv"), "--output", "-o"),
) -> None:
    """Procesa todos los archivos SPM de una carpeta → tabla resumen CSV."""
    from spmkit.core import batch as batch_mod

    files = batch_mod.find_files(folder)
    if not files:
        console.print("[yellow]No hay archivos SPM soportados en la carpeta.[/]")
        raise typer.Exit(1)
    result = batch_mod.process(files, channel=channel)
    result.to_csv(output)
    console.print(f"[green]✓[/] {result.n_ok} ok, {result.n_failed} con error → {output}")


@app.command()
def figure(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid/.nhf/.gwy"),
    channel: str = typer.Option("Z-Axis", "--channel", "-c"),
    output: Path = typer.Option(Path("figure.png"), "--output", "-o", help="png|svg|pdf"),
    colormap: str = typer.Option("batlow", "--colormap"),
    title: str = typer.Option("", "--title"),
) -> None:
    """Exporta una figura de publicación (con scale bar y colormap científico)."""
    from spmkit.core.viz import FigureSpec, save_figure

    data = load(file)
    ch = data[channel]
    spec = FigureSpec(
        title=title or ch.name, colormap=colormap, colorbar_label=f"{ch.name} ({ch.unit})"
    )
    save_figure(ch, spec, output)
    console.print(f"[green]✓[/] Figura → {output}")


@app.command()
def convert(
    file: Path = typer.Argument(..., exists=True, help="Archivo de entrada"),
    output: Path = typer.Argument(..., help="Archivo de salida (.gwy o .h5)"),
) -> None:
    """Convierte entre formatos (p.ej. .nid → .gwy para abrir en Gwyddion)."""
    data = load(file)
    suffix = output.suffix.lower()
    if suffix == ".gwy":
        from spmkit.core.io import save_gwy

        save_gwy(data, output)
    elif suffix in (".h5", ".hdf5"):
        from spmkit.core.export import to_hdf5

        to_hdf5(data, output)
    else:
        raise typer.BadParameter("Formato de salida soportado: .gwy, .h5")
    console.print(f"[green]✓[/] {file.name} → {output}")


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
