#!/bin/bash -e

prof="/tmp/`uuidgen`.prof"
out="callgraph-$(tr ' /' '-#' <<< $*).svg"

python3 -m cProfile -o $prof $@
gprof2dot -f pstats $prof | dot -Tsvg -o $out
rm $prof
