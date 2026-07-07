# Marca — Fathom

**Fathom** es el nombre del *workspace* de curvas de fuerza. **spmkit** es el motor
(librería + CLI) que lo impulsa. La relación es deliberada:

> **Fathom** — el producto que ve el usuario (reemplazo de Nanosurf ANA / JPK).
> **spmkit** — el toolkit open-source debajo (`pip install spmkit`, `spmkit …`).

La identidad del producto vive en una sola fuente: [`src/spmkit/gui/design/brand.py`](https://github.com/kegouro/spmkit/blob/main/src/spmkit/gui/design/brand.py).
Para renombrar el producto se cambia `PRODUCT_NAME` allí.

## El nombre

*Fathom* (braza; "sondear la profundidad") tiene doble lectura, exacta para
nanoindentación: la **profundidad de indentación δ** es lo que se mide, y *to fathom*
es **comprender a fondo**. Lema:

- **ES** — *Curvas de fuerza, a fondo.*
- **EN** — *Force curves, fathomed.*

## Sistema visual — "Instrumento" elevado

Grafito de precisión + teal de señal, con un **oro cálido** de acento (guiño al oro
NanoSurf y a la rama *retract* de las curvas). Mismos tokens que la UI
([`design/tokens.py`](https://github.com/kegouro/spmkit/blob/main/src/spmkit/gui/design/tokens.py)).

| Rol | Hex | Token |
|-----|-----|-------|
| Grafito (fondo) | `#0B0E13` | `bg` |
| Teal (señal / ajuste) | `#2DD4BF` | `accent` |
| Oro (marca / contacto) | `#E8A94B` | `accent_2` |
| Texto | `#E8EEF5` | `text` |
| Texto tenue | `#93A0AE` | `text_muted` |

Tipografía: sans nativa del sistema para el wordmark; mono tabular para cifras y
bylines. Sin degradados agresivos ni *halation*: el teal se reserva al trazo de la
curva, nunca de fondo.

## Logotipo

El símbolo es una **curva de fuerza**: línea base (approach, gris) → **punto de
contacto** (oro) → **curva de carga** (teal). Es a la vez marca y explicación de lo
que hace el producto.

| Archivo | Uso |
|---------|-----|
| [`brand/fathom_mark.svg`](images/brand/fathom_mark.svg) | Símbolo solo (favicon, app icon) |
| [`brand/fathom_lockup.svg`](images/brand/fathom_lockup.svg) | Símbolo + wordmark (docs, "Acerca de") |
| [`brand/fathom_banner.svg`](images/brand/fathom_banner.svg) | Banner ancho (hero del README) |

Reglas: no estirar ni recolorear el teal/oro; mantener el aire alrededor del símbolo;
sobre fondos claros usar las versiones con tile grafito (los SVG ya lo traen).

## Voz

Precisa, sobria, de instrumento científico. Bilingüe ES/EN sin traducir de más.
Afirma resultados con su evidencia (R², σ); nunca exagera la certeza.

> Antes de un lanzamiento público, verificar que el nombre "Fathom" no colisione con
> marcas registradas en el dominio de instrumentación científica.
