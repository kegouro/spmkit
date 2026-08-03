# GwyCompat Source Audit Foundation

## Status and boundary

`spmkit.compat.gwyddion` is a conservative source-compatible migration and audit layer. This
foundation inventories supplied Gwyddion C source text statically; it does not compile, execute,
translate, import, or load a Gwyddion module or shared object. It provides no binary
compatibility and does not claim that a complete module is portable because a registration or
symbol is recognized.

The initial profile is limited to frozen Gwyddion 2.71 source. It recognizes module-query macros,
the registered process/tool families, Gwyddion prefixes, and GTK/GLib dependencies. The only
explicit current mappings are data-model facts already represented by `SPMChannel`: x/y
resolution and x/y physical ranges. All other symbols remain `adapter-required`, `unsupported`,
or `unknown` as reported; similar names never establish support.

## Static audit contract

The lexical scanner preserves line/column locations, local and system includes, multiline calls,
registration-looking calls, Gwyddion symbols, and GTK/GLib dependencies. It masks comments and
string/character literal contents before detecting symbols and distinguishes function-like calls
from plain references. It deduplicates each symbol while retaining all ordered occurrences.

This is not a complete C parser. It does not preprocess macros, resolve types, evaluate control
flow, prove mutation, or infer scientific semantics. UI, selection, parameter, publication, and
mutation results are named conservative audit hints. The report is deterministic JSON-compatible
data with a source content SHA-256 and a schema version; the core auditor performs no filesystem
writes.

## Migration and licensing rules

GwyCompat does not copy GPL implementation bodies and does not automatically translate scientific
algorithms. License compatibility must be reviewed for every proposed migrated module. Numerical
equivalence remains subject to the established workflow:

```text
source → external probe → independent oracle → SPMKit implementation → validation
```

The closed Flatten Base, Arc, Sphere, Median Background, Flat-Disc, and Path Level specifications
remain scientific evidence for their individual capabilities. They are not a general source
migration authorization. Future data-field, selection, parameter, and publication adapters must
be designed, tested, and licensed independently before a report can move beyond static inventory.
