#!/usr/bin/env bash
# Reproducible Linux-only test dependency build; no CAEL/runtime modification.
set -euo pipefail
root="${1:?Pass a new build directory}"
prefix="$root/install"
mkdir -p "$root/logs" "$prefix"
python_bin=/usr/bin/python3
python_site="$prefix/lib/python-site"
pins="$(cd "$(dirname "$0")" && pwd)/UPSTREAM_PINS.json"
for project in cogutil atomspace; do
  revision="$($python_bin -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$pins" "$project")"
  git clone --no-checkout --filter=blob:none "https://github.com/opencog/$project.git" "$root/$project"
  git -C "$root/$project" fetch --depth 1 origin "$revision"
  git -C "$root/$project" checkout --detach "$revision"
  test "$(git -C "$root/$project" rev-parse HEAD)" = "$revision"
  cp "$root/$project/LICENSE" "$root/logs/$project-LICENSE"
  cmake -S "$root/$project" -B "$root/$project-build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DCMAKE_PREFIX_PATH="$prefix" -DPython3_EXECUTABLE="$python_bin" \
    -DPYTHON_INSTALL_PREFIX="$python_site" \
    -DGUILE_SITE_DIR="$prefix/share/guile/site/3.0" \
    -DGUILE_SITE_CCACHE_DIR="$prefix/lib/guile/3.0/site-ccache" \
    2>&1 | tee "$root/logs/$project-configure.log"
  cmake --build "$root/$project-build" --parallel 2 2>&1 | tee "$root/logs/$project-build.log"
  # Upstream also installs /etc/ld.so.conf.d/opencog.conf regardless of prefix.
  # Installation privileges are required; use an isolated Linux runner.
  sudo cmake --install "$root/$project-build" 2>&1 | tee "$root/logs/$project-install.log"
  sudo ldconfig
done
PYTHONPATH="$python_site" LD_LIBRARY_PATH="$prefix/lib/opencog:$prefix/lib" \
  "$python_bin" -c 'import opencog.atomspace as a; print(a.__file__); print(a.AtomSpace())'
