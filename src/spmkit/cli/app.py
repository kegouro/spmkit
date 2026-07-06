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
from spmkit.core.analysis import kpfm, leveling, roughness, spectral
from spmkit.core.export import to_csv, to_json
from spmkit.core.verify import trace_nid

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


@app.command(name="psd")
def psd_cmd(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid o .nhf"),
    channel: str = typer.Option("Z-Axis", "--channel", "-c", help="Canal a analizar"),
) -> None:
    """Análisis espectral: dimensión fractal, Hurst y longitud de correlación."""
    data = load(file)
    ch = data[channel]
    ch = leveling.plane_fit(ch)
    frac = spectral.fractal_dimension(ch)
    corr = spectral.correlation_length(ch)
    table = Table(title=f"Espectral · {channel} · {file.name}")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("Dimensión fractal D", f"{frac.fractal_dimension:.4f}")
    table.add_row("Exponente de Hurst H", f"{frac.hurst:.4f}")
    table.add_row("Pendiente β (PSD)", f"{frac.psd_slope:.4f}")
    table.add_row("R² (ajuste log-log)", f"{frac.r_squared:.4f}")
    table.add_row("Longitud de correlación", f"{corr * 1e9:.2f} nm")
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
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone|dmt"),
    contact_method: str = typer.Option(
        "threshold", "--contact-method", help="Detección de contacto: threshold|rov"
    ),
    spring_constant: float | None = typer.Option(
        None,
        "--spring-constant",
        help="Constante de resorte del cantiléver (N/m) para corregir la indentación",
    ),
) -> None:
    """Ajusta una curva fuerza-distancia (Hertz/DMT/Sneddon) y estima el módulo de Young."""
    from spmkit.core.analysis import mechanics

    data = load(file)
    ch = data[channel]
    curves = mechanics.extract_curves(ch)
    if not curves:
        console.print("[red]No se encontraron curvas en el canal.[/]")
        raise typer.Exit(1)
    idx = len(curves) // 2 if curve < 0 else curve
    if not 0 <= idx < len(curves):
        console.print(f"[red]Curva {idx} fuera de rango (0..{len(curves) - 1}).[/]")
        raise typer.Exit(1)
    result = mechanics.fit_hertz(
        curves[idx],
        tip_radius=tip_radius,
        model=model,
        contact_method=contact_method,
        spring_constant=spring_constant,
    )
    e_mpa = result.young_modulus / 1e6
    e_std_mpa = result.young_modulus_std / 1e6
    table = Table(title=f"Nanomecánica · curva {idx}/{len(curves)} · {model}")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("Módulo de Young", f"{e_mpa:.4g} ± {e_std_mpa:.2g} MPa")
    table.add_row("R²", f"{result.r_squared:.5f}")
    table.add_row("Punto de contacto", f"{result.contact_point * 1e9:.2f} nm")
    table.add_row("Adhesión", f"{result.adhesion * 1e9:.3g} nN")
    table.add_row("RMSE", f"{result.rmse:.3e}")
    table.add_row("Puntos ajustados", str(result.n_fit))
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
    position: float = typer.Option(
        1.0, "--position", "-x", help="Posición de carga x/L (micrografía); k(x)=k(L)/(x/L)³"
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
    import numpy as _np  # noqa: PLC0415

    ev = resonance.load_evaporation_series(
        files, spring_constant=spring_constant, x_over_l=position
    )

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
        f"[cyan]Masa de la masa añadida (Δm inicial):[/] {ev.added_mass[0] * 1e12:.3f} ng"
    )

    # Ajuste ley d² (evaporación limitada por difusión)
    radios = resonance.droplet_radius(ev.added_mass)
    d2 = resonance.fit_d2_law(ev.time, radios)
    tau_h = d2.tau / 3600.0 if _np.isfinite(d2.tau) else float("inf")
    K_um2_s = d2.rate_constant * 1e12  # m²/s → µm²/s
    r0_um = d2.r0 * 1e6  # m → µm
    diff_label = "[green]Sí[/]" if d2.is_diffusion_limited else "[yellow]No[/]"

    d2_table = Table(title="Ley d² (evaporación por difusión)")
    d2_table.add_column("Parámetro", style="cyan")
    d2_table.add_column("Valor", justify="right")
    d2_table.add_row("r₀ (radio inicial)", f"{r0_um:.2f} µm")
    d2_table.add_row("τ (tiempo total)", f"{tau_h:.2f} h")
    d2_table.add_row("K (constante)", f"{K_um2_s:.4g} µm²/s")
    d2_table.add_row("R²", f"{d2.r_squared:.4f}")
    d2_table.add_row("Difusión limitada", diff_label)
    console.print(d2_table)
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
def verify(
    file: Path = typer.Argument(..., exists=True, help="Archivo .nid a verificar"),
) -> None:
    """Verifica la integridad y trazabilidad de un archivo .nid."""
    trace = trace_nid(file)

    # Tabla de canales
    ch_table = Table(title=f"Canales · {file.name}")
    ch_table.add_column("Canal", style="cyan")
    ch_table.add_column("Offset", justify="right")
    ch_table.add_column("Bytes", justify="right")
    ch_table.add_column("Forma", justify="right")
    ch_table.add_column("Unidad")
    ch_table.add_column("Raw min", justify="right")
    ch_table.add_column("Raw max", justify="right")
    ch_table.add_column("Fís min", justify="right")
    ch_table.add_column("Fís max", justify="right")
    ch_table.add_column("Volt", justify="center")
    for ch in trace.channels:
        ch_table.add_row(
            ch.name,
            f"{ch.byte_offset:,}",
            f"{ch.byte_length:,}",
            f"{ch.lines}×{ch.points}",
            ch.dim2_unit,
            f"{ch.raw_min:.4g}",
            f"{ch.raw_max:.4g}",
            f"{ch.phys_min:.4g}",
            f"{ch.phys_max:.4g}",
            "Sí" if ch.flipped else "No",
        )
    console.print(ch_table)

    # Tabla de verificaciones
    chk_table = Table(title="Verificaciones de integridad")
    chk_table.add_column("Estado", justify="center")
    chk_table.add_column("Nombre")
    chk_table.add_column("Detalle", style="dim")
    for chk in trace.checks:
        mark = "[green]✓[/]" if chk.passed else "[red]✗[/]"
        chk_table.add_row(mark, chk.name, chk.detail)
    console.print(chk_table)

    # Resultado global
    if trace.ok:
        console.print("\n[bold green]VERIFICACIÓN OK[/bold green]")
    else:
        failed = [c.name for c in trace.checks if not c.passed]
        console.print("\n[bold red]VERIFICACIÓN FALLIDA[/bold red]")
        for name in failed:
            console.print(f"  [red]✗[/] {name}")
        raise typer.Exit(1)


@app.command()
def gui() -> None:
    """Lanza la interfaz gráfica clásica (requiere el extra 'gui')."""
    try:
        from spmkit.gui.app import run

        run()
    except ImportError:
        console.print("[red]La GUI requiere PyQt6. Instala con:[/] pip install 'spmkit[gui]'")
        raise typer.Exit(code=1) from None


@app.command()
def workspace(
    file: Path | None = typer.Argument(None, help="Archivo de curvas a abrir al arrancar"),
) -> None:
    """Lanza el nuevo workspace de curvas de fuerza (rediseño; requiere 'gui')."""
    try:
        from spmkit.gui.app_workspace import run
    except ImportError:
        console.print("[red]El workspace requiere PyQt6. Instala con:[/] pip install 'spmkit[gui]'")
        raise typer.Exit(code=1) from None
    raise typer.Exit(code=run(str(file) if file else None))


def _apply_level(ch, level: str):  # type: ignore[no-untyped-def]
    if level == "plane":
        return leveling.plane_fit(ch)
    if level == "poly":
        return leveling.polynomial(ch, order=2)
    if level == "none":
        return ch
    raise typer.BadParameter("level debe ser plane|poly|none")


def _force_recipe(model: str, tip_radius: float, recipe_path: Path | None = None):  # type: ignore[no-untyped-def]
    """Recipe de un archivo YAML (reproducible) o el pipeline por defecto."""
    from spmkit.core.pipeline import Recipe, Step

    if recipe_path is not None:
        return Recipe.from_yaml(recipe_path.read_text(encoding="utf-8"))
    return Recipe(
        steps=(
            Step(op="find_contact_point"),
            Step(
                op="fit_elasticity",
                params={"model": model, "tip_radius": tip_radius},
                condition="contact_detected",
            ),
        )
    )


@app.command()
def forcecurve(
    file: Path = typer.Argument(..., exists=True, help="Archivo .jpk-force o .nid"),
    curve: int = typer.Option(0, "--curve", help="Índice de curva (para force-volume)"),
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone|dmt"),
    tip_radius: float = typer.Option(10e-9, "--tip-radius", help="Radio de punta (m)"),
) -> None:
    """Ajusta una curva de fuerza (JPK/NanoSurf) y reporta el módulo, R², adhesión."""
    from spmkit.core.io import load_any
    from spmkit.core.pipeline import run

    vol = load_any(file, "force")[0]
    if not 0 <= curve < vol.n_curves:
        console.print(f"[red]Curva {curve} fuera de rango (0..{vol.n_curves - 1}).[/]")
        raise typer.Exit(1)
    _, ctx = run(_force_recipe(model, tip_radius), vol.curve(curve))
    if "young_modulus" not in ctx:
        console.print("[yellow]No se detectó contacto; no se ajustó.[/]")
        raise typer.Exit(1)
    e, es = ctx["young_modulus"] / 1e3, ctx["young_modulus_std"] / 1e3
    table = Table(title=f"Curva de fuerza · {file.name} · {curve}/{vol.n_curves} · {model}")
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("Módulo de Young", f"{e:.4g} ± {es:.2g} kPa")
    table.add_row("R²", f"{ctx['r_squared']:.4f}")
    table.add_row("Adhesión", f"{ctx['adhesion'] * 1e9:.3g} nN")
    if ctx.get("dissipation") is not None:
        table.add_row("Disipación", f"{ctx['dissipation'] * 1e15:.3g} fJ")
    console.print(table)


@app.command()
def forcemap(
    file: Path = typer.Argument(..., exists=True, help="Force-volume .nid"),
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone|dmt"),
    tip_radius: float = typer.Option(10e-9, "--tip-radius", help="Radio de punta (m)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="CSV del mapa de módulo"),
    figure: Path | None = typer.Option(None, "--figure", "-f", help="PNG de los mapas"),
    parallel: bool = typer.Option(False, "--parallel", help="Pipeline por curva en paralelo"),
    fast: bool = typer.Option(True, "--fast/--pipeline", help="Ruta vectorizada (rápida)"),
    backend: str = typer.Option("cpu", "--backend", help="cpu|gpu (ruta rápida)"),
) -> None:
    """Analiza un force-volume y muestra la estadística de los mapas de propiedades."""
    import numpy as np

    from spmkit.core.analysis.forcevolume import analyze_volume
    from spmkit.core.analysis.forcevolume_fast import elasticity_map
    from spmkit.core.io import load_any

    vol = load_any(file, "force")[0]
    if fast:
        result = elasticity_map(vol, tip_radius=tip_radius, model=model, backend=backend)
    else:
        result = analyze_volume(vol, _force_recipe(model, tip_radius), parallel=parallel)
    rows, cols = vol.grid_shape
    table = Table(
        title=f"Force-volume · {file.name} · {rows}×{cols} · {result.n_ok}/{vol.n_curves} ok"
    )
    table.add_column("Propiedad", style="cyan")
    table.add_column("Mediana", justify="right")
    table.add_column("σ", justify="right")
    e = result.stats("young_modulus")
    table.add_row("Módulo (kPa)", f"{e['median'] / 1e3:.3g}", f"{e['std'] / 1e3:.2g}")
    a = result.stats("adhesion")
    table.add_row("Adhesión (nN)", f"{a['median'] * 1e9:.3g}", f"{a['std'] * 1e9:.2g}")
    console.print(table)
    if output is not None:
        np.savetxt(output, result.maps["young_modulus"], delimiter=",")
        console.print(f"[green]✓[/] Mapa de módulo → {output}")
    if figure is not None:
        from spmkit.core.viz.maps import save_property_maps

        save_property_maps(result.maps, figure, title=file.name)
        console.print(f"[green]✓[/] Figura de mapas → {figure}")


@app.command()
def forcereport(
    file: Path = typer.Argument(..., exists=True, help="Force-volume .nid o curva de fuerza"),
    output: Path = typer.Option(Path("informe"), "--output", "-o", help="Ruta base del informe"),
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone|dmt"),
    tip_radius: float = typer.Option(10e-9, "--tip-radius", help="Radio de punta (m)"),
    formats: str = typer.Option(
        "html,pdf", "--formats", help="html,latex,pdf (separados por coma)"
    ),
    backend: str = typer.Option("cpu", "--backend", help="cpu|gpu (ruta vectorizada)"),
) -> None:
    """Genera un informe magistral (HTML/LaTeX/PDF) de un force-volume."""
    from spmkit.core.forcereport import build_force_report
    from spmkit.core.io import load_any

    vol = load_any(file, "force")[0]
    fmts = tuple(f.strip().lower() for f in formats.split(",") if f.strip())
    produced = build_force_report(
        vol,
        output,
        source_name=file.name,
        model=model,
        tip_radius=tip_radius,
        backend=backend,
        formats=fmts,
    )
    for fmt, path in produced.items():
        console.print(f"[green]✓[/] {fmt.upper()} → {path}")
    if "pdf" in fmts and "pdf" not in produced:
        console.print("[yellow]![/] PDF omitido: instala una cadena LaTeX (tectonic/pdflatex).")


@app.command()
def forceexport(
    file: Path = typer.Argument(..., exists=True, help="Force-volume .nid o curva de fuerza"),
    output: Path = typer.Option(Path("export"), "--output", "-o", help="Carpeta de salida"),
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone|dmt"),
    tip_radius: float = typer.Option(10e-9, "--tip-radius", help="Radio de punta (m)"),
    backend: str = typer.Option("cpu", "--backend", help="cpu|gpu"),
    no_report: bool = typer.Option(False, "--no-report", help="Omite el informe HTML/PDF"),
) -> None:
    """Exporta TODO (mapas CSV, tabla por curva, resumen e informe) a una carpeta."""
    from spmkit.core.forceexport import export_bundle
    from spmkit.core.io import load_any

    vol = load_any(file, "force")[0]
    fmts: tuple[str, ...] = () if no_report else ("html", "pdf")
    manifest = export_bundle(
        vol,
        output,
        source_name=file.name,
        model=model,
        tip_radius=tip_radius,
        backend=backend,
        report_formats=fmts,
    )
    console.print(f"[green]✓[/] {len(manifest)} archivos exportados → {output}")


@app.command()
def fbatch(
    folder: Path = typer.Argument(..., exists=True, file_okay=False, help="Carpeta de curvas"),
    output: Path = typer.Option(Path("force_batch.csv"), "--output", "-o", help="CSV resumen"),
    model: str = typer.Option("sphere", "--model", help="sphere|paraboloid|cone|dmt"),
    tip_radius: float = typer.Option(10e-9, "--tip-radius", help="Radio de punta (m)"),
    parallel: bool = typer.Option(False, "--parallel", help="Ejecución en paralelo"),
    recipe: Path | None = typer.Option(None, "--recipe", help="Recipe YAML reproducible"),
) -> None:
    """Procesa por lotes todas las curvas de fuerza de una carpeta → CSV resumen."""
    from spmkit.core.forcebatch import process_force_folder

    result = process_force_folder(
        folder, _force_recipe(model, tip_radius, recipe), parallel=parallel
    )
    result.to_csv(output)
    console.print(
        f"[green]✓[/] {len(result.rows)} archivos ({result.n_failed} con error) → {output}"
    )
    for r in result.rows[:20]:
        if r.error:
            console.print(f"  [red]{r.source}: {r.error}[/]")
        else:
            console.print(
                f"  {r.source}: {r.n_curves} curvas · E={r.young_modulus_median / 1e3:.3g} kPa"
            )


if __name__ == "__main__":
    app()
