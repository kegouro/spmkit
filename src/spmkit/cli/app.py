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
    spring_constant: float | None = typer.Option(
        None,
        "--spring-constant",
        help="Constante de resorte del cantiléver (N/m) para corregir la indentación",
    ),
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
    result = mechanics.fit_hertz(
        curves[idx], tip_radius=tip_radius, model=model, spring_constant=spring_constant
    )
    table = Table(title=f"Nanomecánica · curva {idx}/{len(curves)} · {model}")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("Módulo de Young", f"{result.young_modulus / 1e6:.4g} MPa")
    table.add_row("Punto de contacto", f"{result.contact_point * 1e9:.2f} nm")
    table.add_row("Adhesión", f"{result.adhesion * 1e9:.3g} nN")
    table.add_row("RMSE", f"{result.rmse:.3e}")
    console.print(table)


@app.command(name="grains")
def grains_cmd(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid o .nhf"),
    channel: str = typer.Option("Z-Axis", "--channel", "-c", help="Canal de topografía"),
    threshold: float | None = typer.Option(
        None, "--threshold", "-t", help="Umbral de altura en unidades del canal (None = auto)"
    ),
    min_size: int = typer.Option(4, "--min-size", help="Tamaño mínimo de grano en píxeles"),
    relative_height: float = typer.Option(
        0.5, "--relative-height", help="Fracción para umbral automático (0..1]"
    ),
) -> None:
    """Detecta granos/partículas y muestra estadísticas de tamaño."""
    from spmkit.core.analysis import grains

    data = load(file)
    ch = data[channel]
    ch = leveling.plane_fit(ch)
    result = grains.detect(
        ch, threshold=threshold, min_size=min_size, relative_height=relative_height
    )

    table = Table(title=f"Granos · {channel} · {file.name}")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("N.º de granos", str(result.n_grains))
    table.add_row("Diámetro medio", f"{result.mean_diameter * 1e9:.2f} nm")
    table.add_row("Densidad", f"{result.density:.4g} granos/µm²")
    table.add_row("Cobertura", f"{result.coverage * 100:.2f} %")
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
def evaporation(
    folder: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Carpeta con espectros de thermal tuning (.nid)"
    ),
    spring_constant: float | None = typer.Option(
        None,
        "--spring-constant",
        "-k",
        help="Constante de resorte (N/m); por defecto, la del archivo",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="CSV de salida"),
) -> None:
    """Sensado de masa por evaporación: sigue f(t) → masa y tasa de evaporación."""
    import csv as _csv

    from spmkit.core.analysis import resonance

    files = sorted(folder.glob("*.nid"))
    if len(files) < 2:
        console.print("[red]Se necesitan al menos 2 espectros de thermal tuning.[/]")
        raise typer.Exit(1)
    ev = resonance.load_evaporation_series(files, spring_constant=spring_constant)

    table = Table(
        title=f"Evaporación · k={ev.spring_constant:.3g} N/m · "
        f"f₀ desnuda={ev.bare_frequency / 1e3:.1f} kHz"
    )
    for col in ("t (h)", "f (kHz)", "m_eff (ng)", "Δm (ng)", "tasa (ng/h)"):
        table.add_column(col, justify="right")
    for i in range(len(ev.time)):
        table.add_row(
            f"{ev.time[i] / 3600:.2f}",
            f"{ev.frequency[i] / 1e3:.2f}",
            f"{ev.mass[i] * 1e12:.3f}",
            f"{ev.added_mass[i] * 1e12:.3f}",
            f"{ev.evaporation_rate[i] * 1e12 * 3600:.3f}",
        )
    console.print(table)
    console.print(
        f"[cyan]Masa de la liquid marble (Δm inicial):[/] {ev.added_mass[0] * 1e12:.3f} ng"
    )
    if output:
        with output.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["time_s", "frequency_Hz", "mass_kg", "added_mass_kg", "evap_rate_kg_s"])
            for i in range(len(ev.time)):
                w.writerow(
                    [
                        ev.time[i],
                        ev.frequency[i],
                        ev.mass[i],
                        ev.added_mass[i],
                        ev.evaporation_rate[i],
                    ]
                )
        console.print(f"[green]✓[/] CSV → {output}")


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
