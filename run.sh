#!/bin/sh
if test $# -lt 1 ; then
    echo 1>&2 "Need a command: rebuild or extract."
    exit 1
fi
cmd=$1
shift
case "$cmd" in
    rebuild|extract)
        ;;
    *)
        echo 1>&2 "Unrecognized command."
        exit 1
        ;;
esac
here=`dirname $0`
PYTHONPATH="${here}" exec python3 -m "doublegit.${cmd}" "$@"
