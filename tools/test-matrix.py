#!/usr/bin/env python3
"""Port + test many themes, on one or more layout baselines, in parallel test routers 1..W.

  test-matrix.py [THEME ...] [--baseline bootstrap,argon] [--workers 4] [--quick | --tune N] [--table-only]

Default: every theme in src/themes on the bootstrap baseline. Each job runs
port-theme.py THEME --baseline B --test --force (rack on bootstrap: the hand port as
it is); --quick runs port-theme.py --quick instead (install + a11y, no regeneration).
Logs: dist/ports/logs/<id>.log. Afterwards dist/ports/MATRIX.md is rebuilt from every
TEST-SUMMARY.txt found (all themes and baselines), so it always shows the latest state.
env: SUDO as for port-theme.py.
"""
import argparse, glob, os, queue, re, shlex, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baselines
from baselines import ROOT

PORTS = os.path.join(ROOT, "dist/ports")


def summaries():
    """(id, path) of every full test summary"""
    out = [("rack21", os.path.join(ROOT, "dist/screenshots/TEST-SUMMARY.txt"))]
    out += [(os.path.basename(os.path.dirname(p)), p) for p in glob.glob(f"{PORTS}/*/TEST-SUMMARY.txt")]
    order = lambda i: baselines.NAMES.index(i.partition("-")[2] or baselines.native_baseline(i[:-2]) or "bootstrap")
    return sorted(((i, p) for i, p in out if os.path.exists(p)), key=lambda x: (order(x[0]), x[0]))


def write_matrix():
    rows = ["| Theme | Baseline | Package | Layout | Console | Phone menu | Reduced motion | AA contrast | Functional A/B | Install/remove | Tested |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for tid, p in summaries():
        s = open(p, encoding="utf-8").read()
        g = lambda pre: (re.search(rf"^{pre}.*?\b(PASS|FAIL)", s, re.M) or [None, "-"])[1]
        size = re.search(r"^package: \S+ (\d+) bytes", s, re.M)
        when = re.search(r"^== \S+\s+\((\d{4}-\d\d-\d\d)", s, re.M)
        inst = "FAIL" if re.search(r"^(install|remove|leftover).*FAIL", s, re.M) else "PASS"
        con = (re.search(r"^WCAG AA contrast: (.*)$", s, re.M) or [None, "-"])[1]
        base = re.search(r"^== .*baseline (\w+)\)", s, re.M)
        rows.append(f"| {tid} | {base[1] if base else tid.partition('-')[2] or 'bootstrap'} | {int(size[1]) // 1024 if size else '?'} KB | "
                    f"{g('layout')} | {g('console')} | {g('phone menu')} | {g('reduced')} | {con} | "
                    f"{g('functional')} | {inst} | {when[1] if when else '?'} |")
    text = f"# Theme port test matrix\n\nOne row per package; rebuilt by tools/test-matrix.py from each TEST-SUMMARY.txt.\n\n" + "\n".join(rows) + "\n"
    with open(f"{PORTS}/MATRIX.md", "w", newline="\n") as f:
        f.write(text)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("themes", nargs="*")
    ap.add_argument("--baseline", default="bootstrap", help="comma list of: " + ", ".join(baselines.NAMES))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 4)))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--tune", type=int, default=0, metavar="N",
                    help="before the full test, up to N rounds of: --quick, contrast-fix.py (theme's css/35-*.css)")
    ap.add_argument("--table-only", action="store_true", help="only rebuild MATRIX.md")
    a = ap.parse_args()
    if a.table_only:
        print(write_matrix())
        return
    bases = a.baseline.split(",")
    for b in bases:
        baselines.get(b)
    themes = a.themes or sorted(d[len("luci-theme-"):] for d in os.listdir(baselines.THEMES) if d.startswith("luci-theme-"))
    jobs = queue.Queue()
    for b in bases:
        for t in themes:
            jobs.put((t, b))
    sudo = os.environ.get("SUDO", "sudo")
    pre = shlex.split(sudo)
    for i in range(1, a.workers + 1):
        r = subprocess.run(pre + ["docker", "inspect", "-f", "{{.State.Running}}", f"luci21-opt-{i}"], capture_output=True, text=True)
        if r.stdout.strip() != "true":
            subprocess.run(pre + ["env", f"INSTANCE={i}", "sh", os.path.join(ROOT, "testenv/up.sh")], check=True)
    os.makedirs(f"{PORTS}/logs", exist_ok=True)
    results, lock = [], threading.Lock()

    def worker(i):
        while True:
            try:
                t, b = jobs.get_nowait()
            except queue.Empty:
                return
            tid = baselines.theme_id(t, b)
            pt = [sys.executable, "-I", os.path.join(ROOT, "tools/port-theme.py"), t, "--baseline", b, "--instance", str(i)]
            run = lambda cmd, log: subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, SUDO=sudo)).returncode
            t0 = time.time()
            with open(f"{PORTS}/logs/{tid}.log", "w") as log:
                if a.tune and not os.path.isdir(baselines.package_dir(t, b)):
                    run(pt, log)                                   # generate first
                for n in range(a.tune):
                    if run(pt + ["--quick"], log) == 0:
                        break
                    print(f"## tune round {n + 1}: contrast-fix", file=log, flush=True)
                    run([sys.executable, "-I", os.path.join(ROOT, "tools/contrast-fix.py"), t, "--baseline", b], log)
                rc = run(pt + (["--quick"] if a.quick else ["--test", "--force"]), log)
                summ = os.path.join(PORTS, tid, "TEST-SUMMARY.txt")
                if a.tune and rc == 1 and os.path.exists(summ):
                    fails = [l for l in open(summ) if "FAIL" in l]
                    if fails and all(l.startswith("WCAG") for l in fails):
                        # pages with varying content (routes, leases) can show a failing text the
                        # quick runs did not: fix from the full run and test once more
                        print("## contrast-fix from the full run", file=log, flush=True)
                        run([sys.executable, "-I", os.path.join(ROOT, "tools/contrast-fix.py"), t, "--baseline", b], log)
                        rc = run(pt + ["--test"], log)
            with lock:
                results.append((tid, rc))
                print(f"{tid:28} {'PASS' if rc == 0 else 'FAIL' if rc == 1 else f'ERROR {rc}'}  "
                      f"(router {i}, {time.time() - t0:.0f}s)", flush=True)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(1, a.workers + 1)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    if not a.quick:
        print(write_matrix())
    sys.exit(0 if all(rc == 0 for _, rc in results) else 1)


if __name__ == "__main__":
    main()
