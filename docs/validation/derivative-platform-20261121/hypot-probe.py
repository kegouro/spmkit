from pathlib import Path
import ctypes, ctypes.util, hashlib, json, platform, subprocess
from decimal import Decimal, localcontext
import numpy as np
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--library", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
npz = (
    root / "tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz"
)
arrays = dict(np.load(npz, allow_pickle=False))
lib = ctypes.CDLL(str(args.library.resolve()))
mathlib = ctypes.CDLL(ctypes.util.find_library("m"))
functions = {}
for label, symbol, library in [
    ("generic", "probe_hypot_generic", lib),
    ("fma", "probe_hypot_fma", lib),
    ("local_libm", "hypot", mathlib),
]:
    fn = getattr(library, symbol)
    fn.restype = ctypes.c_double
    fn.argtypes = [ctypes.c_double] * 2
    functions[label] = fn
functions["numpy"] = lambda x, y: float(np.hypot(x, y))


def bits(v):
    return int(np.float64(v).view(np.uint64))


report = {
    "platform": platform.platform(),
    "numpy": np.__version__,
    "compiler": subprocess.check_output(["cc", "--version"], text=True).splitlines()[0],
    "hashes": {},
    "families": {},
    "samples": [],
}
for f in [Path(__file__).with_name("hypot-standalone.c"), args.library, Path(__file__), npz]:
    report["hashes"][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
for family in ["sobel", "prewitt"]:
    stats = {
        label: {
            "elements": 0,
            "bitwise_mismatches_vs_frozen": 0,
            "max_abs_delta_vs_frozen": 0.0,
            "max_ulp_vs_frozen": 0,
            "max_ulp_vs_nearest": 0,
            "outside_faithful_bracket": 0,
            "mismatch_cases": [],
        }
        for label in functions
    }
    count = 0
    cases = 0
    unstable = 0
    invalid_brackets = 0
    for key in arrays:
        if not key.startswith("mag_" + family + "_"):
            continue
        cid = key[len("mag_" + family + "_") :]
        cases += 1
        for i, (a, b, frozen) in enumerate(
            zip(
                arrays[family + "_x_" + cid].ravel(),
                arrays[family + "_y_" + cid].ravel(),
                arrays[key].ravel(),
            )
        ):
            a, b, frozen = map(float, (a, b, frozen))
            count += 1
            da, db = Decimal.from_float(a), Decimal.from_float(b)
            refs = []
            for prec in (100, 180):
                with localcontext() as ctx:
                    ctx.prec = prec
                    refs.append((da * da + db * db).sqrt())
            nearest = float(refs[1])
            unstable += float(refs[0]) != nearest
            with localcontext() as ctx:
                ctx.prec = 4096
                exact_square = da * da + db * db
                dn = Decimal.from_float(nearest)
                if dn * dn == exact_square:
                    lo = hi = nearest
                elif dn * dn < exact_square:
                    lo = nearest
                    hi = float(np.nextafter(nearest, np.inf))
                else:
                    hi = nearest
                    lo = float(np.nextafter(nearest, -np.inf))
                dlow, dhigh = Decimal.from_float(lo), Decimal.from_float(hi)
                invalid_brackets += not dlow * dlow <= exact_square <= dhigh * dhigh
            vals = {name: fn(a, b) for name, fn in functions.items()}
            for name, value in vals.items():
                s = stats[name]
                s["elements"] += 1
                s["max_abs_delta_vs_frozen"] = max(
                    s["max_abs_delta_vs_frozen"], abs(value - frozen)
                )
                s["max_ulp_vs_frozen"] = max(
                    s["max_ulp_vs_frozen"], abs(bits(value) - bits(frozen))
                )
                s["max_ulp_vs_nearest"] = max(
                    s["max_ulp_vs_nearest"], abs(bits(value) - bits(nearest))
                )
                s["outside_faithful_bracket"] += not lo <= value <= hi
                if bits(value) != bits(frozen):
                    s["bitwise_mismatches_vs_frozen"] += 1
                    s["mismatch_cases"].append(
                        {
                            "case": cid,
                            "index": i,
                            "frozen": frozen.hex(),
                            "computed": value.hex(),
                            "ulp": abs(bits(value) - bits(frozen)),
                        }
                    )
            if family == "sobel" and cid in ("C19", "X08") and i in (16, 28):
                report["samples"].append(
                    {
                        "case": cid,
                        "index": i,
                        "x": a.hex(),
                        "y": b.hex(),
                        "frozen": frozen.hex(),
                        "nearest": nearest.hex(),
                        "lower": lo.hex(),
                        "upper": hi.hex(),
                        **{k: v.hex() for k, v in vals.items()},
                    }
                )
    report["families"][family] = {
        "cases": cases,
        "elements": count,
        "precision_unstable": unstable,
        "invalid_exact_squared_brackets": invalid_brackets,
        "backends": stats,
    }
args.output.write_text(json.dumps(report, indent=2))
print(
    json.dumps(
        {
            "families": {
                k: {kk: vv for kk, vv in v.items() if kk != "backends"}
                for k, v in report["families"].items()
            },
            "hashes": report["hashes"],
        },
        indent=2,
    )
)
