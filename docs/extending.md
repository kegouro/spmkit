# Extender spmkit y Fathom

`spmkit` está pensado como un **host multi-física**: un núcleo puro de análisis, una CLI y
un workspace de escritorio (**Fathom**). Fathom es la extensión de AFM/espectroscopía de
fuerza, pero la arquitectura deja los enchufes para que **otros dominios** (u otros
laboratorios) sumen sus propios lectores, análisis y paneles **sin tocar el núcleo**.

Hay tres puntos de extensión, de menor a mayor alcance:

| Quieres añadir… | Punto de extensión | Grupo de entry-point |
|---|---|---|
| Un **formato** o un **análisis** | `core.plugins` (Protocols) | `spmkit.plugins.v1` |
| Una **perspectiva/panel** en Fathom | `gui.extensions` (`ModuleSpec`) | `spmkit.gui.modules` |
| Un **dominio** entero (otro core) | `Domain` + módulos GUI | ambos |

!!! info "La regla que no se rompe"
    `core/` es Python puro **sin imports de UI** (lo hace cumplir `tests/test_architecture.py`).
    Los lectores y análisis viven en `core`; los paneles y ViewModels en `gui`. Un módulo de
    Fathom conecta ambos, pero nunca mete Qt dentro de `core`.

---

## 1. Añadir un módulo a Fathom (paneles + perspectivas)

Un **módulo de workspace** empaqueta lo que aporta una función: sus paneles y sus
perspectivas. `build_workspace` deriva de la lista de módulos **todo** lo demás (barra de
perspectivas, docks, lienzos, cableado). **Añadir un módulo es declarar un `ModuleSpec`.**

```python
from spmkit.gui.extensions import ModuleContext, ModuleSpec, PanelSpec, PerspectiveSpec
from spmkit.gui.panels.base import Panel


def _mi_panel(ctx: ModuleContext) -> Panel:
    # Importa el panel/ViewModel aquí (factory perezosa: no encarece el import del módulo).
    from mi_paquete.panels import MiPanel
    from mi_paquete.viewmodels import MiViewModel

    return MiPanel(MiViewModel(ctx.image_vm))  # cablea al hub de imagen compartido


MI_MODULO = ModuleSpec(
    name="raman",
    panels=(PanelSpec("raman_canvas", "Raman", _mi_panel, area="central"),),
    perspectives=(PerspectiveSpec("raman", "Raman", ("navigator", "raman_canvas")),),
)
```

Con eso aparece la perspectiva **Raman** en la barra, su lienzo central y su comando
"Ir a Raman" en la paleta (⌘K). No se toca la shell.

### Piezas

- **`PanelSpec(key, label, factory, area)`** — `area` es `"central"` (lienzo) o
  `"left"/"right"/"bottom"` (dock). La `factory` recibe el `ModuleContext` y devuelve un
  `Panel`.
- **`PerspectiveSpec(key, label, panels)`** — qué paneles (por clave) muestra la perspectiva.
  Puede referenciar paneles de otros módulos (p. ej. `"navigator"` del módulo *core*).
- **`ModuleContext`** — los *hubs* compartidos (`force_vm`, `image_vm`, `map_vm`, `batch_vm`),
  un `session` para el `.spmproj` y un `store` donde el módulo guarda sus propios ViewModels.
- **`ModuleSpec.wire(ws, ctx)`** *(opcional)* — gancho tras construir la ventana: conecta
  señales del módulo a la shell (estado/progreso) o registra comandos.

### Paneles y ViewModels (MVVM)

Un panel hereda de `spmkit.gui.panels.base.Panel` (trae *sandbox* de errores: si `build()`
falla, muestra una tarjeta de error en vez de tumbar la app). El estado observable va en un
**ViewModel** (`QObject` con señales) que reutiliza el `core` puro. Mira `gui/panels/` y
`gui/viewmodels/` para el patrón.

---

## 2. Publicar un módulo desde otro paquete (entry-point)

No hace falta editar `spmkit`. Publica el `ModuleSpec` en el grupo `spmkit.gui.modules` y
Fathom lo descubre al arrancar:

```toml
# pyproject.toml de tu paquete
[project.entry-points."spmkit.gui.modules"]
raman = "mi_paquete.modulo:MI_MODULO"
```

El valor puede ser un `ModuleSpec` o un *callable* que devuelva uno. Un módulo roto se ignora
sin tumbar la app; ante choque de claves gana el módulo de fábrica (un plugin no pisa a Fathom).

---

## 3. Añadir un formato o un análisis (núcleo)

Los contratos viven en `core/plugins/contracts.py` como `Protocol`s versionados
(`spmkit.plugins.v1`). Un **lector** declara sus extensiones y sabe *inspeccionar* (metadatos
baratos) y *cargar*:

```python
from spmkit.core.plugins.contracts import DatasetInfo, Reader  # Protocols


class MiLector:  # cumple el Protocol Reader (sin heredar)
    extensions: tuple[str, ...] = (".xyz",)

    def inspect(self, path) -> DatasetInfo: ...   # solo cabecera: formato, kinds, canales
    def load(self, path, kind): ...               # devuelve SPMData o ForceVolume
```

Regístralo por entry-point (grupo `spmkit.plugins.v1`) o, para el núcleo, en
`core/plugins/registry.py`. A partir de ahí `load_any(path)`/`inspect_any(path)` lo usan y la
GUI/CLI abren el formato sin cambios. Un **análisis** sigue el mismo patrón con el Protocol
`Analysis`.

---

## 4. Otro core multi-física (dominio)

El Protocol `Domain` (en `core/plugins/contracts.py`) es el enchufe para que un dominio
distinto de AFM (p. ej. Raman, nanoindentación, un instrumento nuevo) se registre como un
core hermano: aporta sus lectores y análisis por `spmkit.plugins.v1` y sus perspectivas por
`spmkit.gui.modules`. Así `spmkit` es el **núcleo del laboratorio** y Fathom **una** de sus
extensiones, no la única.

---

## Checklist para un módulo nuevo

- [ ] Análisis en `core/` (puro, con test en `tests/core/`).
- [ ] ViewModel en `gui/viewmodels/` (estado + señales, reusa `core`).
- [ ] Panel en `gui/panels/` (hereda de `Panel`).
- [ ] `ModuleSpec` en `gui/builtin_modules.py` **o** entry-point `spmkit.gui.modules`.
- [ ] Test que arme el módulo y lo active (ver `tests/gui/test_extensions.py`).
