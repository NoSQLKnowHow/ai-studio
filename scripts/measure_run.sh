#!/usr/bin/env bash
# measure_run.sh: run any command and measure it (DESIGN.md section 46.4, docs/SPARK_TEST.md section 37).
#
#   scripts/measure_run.sh [-i SECONDS] [-o FILE.csv] -- COMMAND [ARGUMENTS...]
#
#   -i, --interval SECONDS   how often to take a sample (default 2; a decimal such as 0.5 is fine)
#   -o, --csv FILE           where to write the samples (default measure_run.csv in the current folder; an
#                            existing file is replaced)
#   -h, --help               this text
#
# What it does. It starts COMMAND, and while the command runs it takes a sample every INTERVAL seconds (and one
# at the start and one at the end, so even a command shorter than the interval has two). A sample is one line of
# the CSV:
#
#   utc_time,elapsed_s,mem_used_mib,mem_available_mib,gpu_mem_used_mib
#
#   mem_used_mib       MemTotal minus MemAvailable from /proc/meminfo: the memory in use on the whole machine,
#                      not only by the command. On the DGX Spark the CPU and the GPU share one pool of memory
#                      (DESIGN.md section 9a), so this is the number that matters there.
#   mem_available_mib  MemAvailable from /proc/meminfo: what the kernel says could still be given to a program
#                      without swapping. Its lowest value is the closest the machine came to running out.
#   gpu_mem_used_mib   the memory nvidia-smi says is in use, summed over the GPUs it lists. Not every machine's
#                      nvidia-smi can say (a unified-memory machine may answer something that is not a number),
#                      which is why the two columns above exist.
#
# A source that is missing (no /proc/meminfo, no nvidia-smi, an nvidia-smi that fails or does not print a number)
# is written as the words "not available" and is never replaced by a guess or by zero. The summary says so too.
#
# At the end it prints one paragraph to the standard error (so that the command's own output, on the standard
# output, can still be piped): the seconds, the peak memory used, the lowest MemAvailable, the peak GPU memory and
# the command's exit status.
#
# Exit status. It is the command's own exit status, unchanged: 0 for success, 7 if the command exited 7, 127 if
# it does not exist, 130 if it was stopped by Ctrl-C. The one thing of its own is 64, for a mistake in how this
# script was called (no command, a bad interval), as sysexits.h names it, so that it is told apart from a command
# that failed.
#
# Stopping. Ctrl-C (or SIGTERM) is passed on to the command, the sampler is stopped, the summary is printed for
# what was measured, and the exit status is the command's (130 after Ctrl-C). The sampler is also stopped on any
# other way out, so no stray background process is left behind.
#
# For the tests only: the environment variable MEASURE_RUN_MEMINFO names a file to read instead of /proc/meminfo, so that a test can give the script a memory
# state it knows, and a missing one.
#
# The command's standard input is closed (it reads from /dev/null): it runs as a background job, which a
# terminal does not let read from the keyboard, and the commands this is for (model runs, ffmpeg) do not ask.
# Because it runs as a job, the shell may print its own notice on the standard error when the command is stopped
# (for example "Interrupt"); it is not from the command.
set -uo pipefail

PROG=measure_run
INTERVAL=2
CSV=measure_run.csv
NA="not available"   # what a source that cannot be read is written as, in the CSV and in the summary

# usage_error MESSAGE: say what was wrong with the call and stop with 64 (see the header). Not used once the command is running.
usage_error() {
  printf '%s: %s\nUsage: %s [-i SECONDS] [-o FILE.csv] -- COMMAND [ARGUMENTS...]\n' "$PROG" "$1" "$0" >&2
  exit 64
}

# print_help: the block of comments at the top of this file, without the shebang line and the "# " in front.
print_help() { sed -n '2,/^set -uo/p' "$0" | sed '$d; s/^# \{0,1\}//'; }

# ------------------------------------------------------------------ the call
while (( $# > 0 )); do
  case $1 in
    -i|--interval) [[ $# -ge 2 ]] || usage_error "$1 needs a number of seconds"; INTERVAL=$2; shift 2 ;;
    -o|--csv)      [[ $# -ge 2 ]] || usage_error "$1 needs a file name"; CSV=$2; shift 2 ;;
    -h|--help)     print_help; exit 0 ;;
    --)            shift; break ;;   # everything after -- is the command, whatever it looks like
    *)             usage_error "unexpected '$1' (put the command after --)" ;;
  esac
done
(( $# > 0 )) || usage_error "no command given (put it after --)"
# a positive number, whole or decimal; anything else would make `sleep` fail inside the sampler and the samples would silently stop
if ! { [[ $INTERVAL =~ ^([0-9]+\.?[0-9]*|\.[0-9]+)$ ]] && awk -v v="$INTERVAL" 'BEGIN { exit !(v > 0) }'; }; then
  usage_error "the interval must be a number of seconds above 0, not '$INTERVAL'"
fi

# the file is made now, so a path that cannot be written is found out before a long command is started, not after it
if ! : > "$CSV" 2>/dev/null; then usage_error "cannot write to '$CSV'"; fi
echo "utc_time,elapsed_s,mem_used_mib,mem_available_mib,gpu_mem_used_mib" >> "$CSV"

# ------------------------------------------------------------------ the sources
# now_s: the time as seconds since 1970 with decimals. $EPOCHREALTIME is bash 5's own clock; the decimal point can be a comma in some languages.
now_s() { if [[ -n ${EPOCHREALTIME:-} ]]; then printf '%s' "${EPOCHREALTIME/,/.}"; else date +%s.%N; fi; }

# mem_fields: "USED_MIB,AVAILABLE_MIB" from /proc/meminfo, each "not available" if /proc/meminfo is missing or lacks the line.
MEMINFO=${MEASURE_RUN_MEMINFO:-/proc/meminfo}   # the variable is for the tests (see the header)
mem_fields() {
  [[ -r $MEMINFO ]] || { printf '%s,%s' "$NA" "$NA"; return; }
  awk -v na="$NA" '
    /^MemTotal:/     { total = $2 }
    /^MemAvailable:/ { avail = $2 }
    END {
      if (total == "" || avail == "") { printf "%s,%s", na, na; exit }
      printf "%.0f,%.0f", (total - avail) / 1024, avail / 1024      # /proc/meminfo is in KiB
    }' "$MEMINFO" 2>/dev/null || printf '%s,%s' "$NA" "$NA"
}

# gpu_field: the GPU memory in use in MiB as nvidia-smi reports it, or "not available" when there is no nvidia-smi, it fails, it takes more than 5
# seconds, or what it prints is not a number. A timeout keeps a hung driver from stopping the samples.
HAVE_NVSMI=0; command -v nvidia-smi >/dev/null 2>&1 && HAVE_NVSMI=1
HAVE_TIMEOUT=0; command -v timeout >/dev/null 2>&1 && HAVE_TIMEOUT=1
gpu_field() {
  (( HAVE_NVSMI )) || { printf '%s' "$NA"; return; }
  local out
  if (( HAVE_TIMEOUT )); then out=$(timeout 5 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null) || { printf '%s' "$NA"; return; }
  else out=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null) || { printf '%s' "$NA"; return; }; fi
  # one line per GPU; they are added up. A line that is not a whole number (for example "[N/A]") makes the whole answer "not available": a sum that left it out would be a guess.
  printf '%s\n' "$out" | awk -v na="$NA" '
    NF == 0 { next }
    { gsub(/[ \t\r]/, "") }
    $0 !~ /^[0-9]+$/ { bad = 1 }
    { sum += $0; seen = 1 }
    END { if (bad || !seen) printf "%s", na; else printf "%d", sum }'
}

START=$(now_s)
# sample: append one line to the CSV. Called by the sampler and, once at the end, by the main part (never both at the same time: the sampler is stopped first).
sample() {
  local at
  at=$(now_s)
  printf '%s,%s,%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(awk -v a="$at" -v s="$START" 'BEGIN { printf "%.2f", a - s }')" "$(mem_fields)" "$(gpu_field)" >> "$CSV"
}

# ------------------------------------------------------------------ run it, with the sampler beside it
# Job control makes each background job its own process group, which does two things we need: a Ctrl-C typed at the terminal reaches this script and
# not the command directly (so the script can stop the sampler and write its summary), and the command does not start with Ctrl-C switched off, as a
# plain background job of a script does. The signal is passed on to the command's own group below.
set -m

sampler=""
child=""
stopped=""  # set to the signal's name when one was passed on, for the summary

# stop_sampler: end the sampler (and the `sleep` it is in the middle of) and wait for it, so the CSV is not written to any more. Safe to call twice.
stop_sampler() {
  if [[ -n $sampler ]]; then
    kill -TERM -- "-$sampler" 2>/dev/null || kill -TERM "$sampler" 2>/dev/null
    wait "$sampler" 2>/dev/null
    sampler=""
  fi
}

# on_exit: the way out of every path. The sampler is stopped here too, so that a script that dies for any reason leaves no process sampling behind. A
# command that is still running at that point (the script was killed in a way that skipped the signal handler's own cleanup) is stopped as well.
# shellcheck disable=SC2329  # called by the trap on the next lines
on_exit() {
  stop_sampler
  if [[ -n $child ]] && kill -0 "$child" 2>/dev/null; then kill -TERM -- "-$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null; fi
}
trap on_exit EXIT

# pass_on SIGNAL: hand a signal this script received to the command's group, and remember it. The script keeps waiting: the command decides whether
# to stop, and when it has, the normal path below stops the sampler, prints the summary and exits with the command's status.
# shellcheck disable=SC2329  # called by the traps below
pass_on() {
  stopped=$1
  [[ -n $child ]] || return 0
  kill -s "$1" -- "-$child" 2>/dev/null || kill -s "$1" "$child" 2>/dev/null
}
trap 'pass_on INT' INT
trap 'pass_on TERM' TERM
trap 'pass_on HUP' HUP

# the sampler: the first line now, then one every INTERVAL seconds. `sleep` is run in the background and waited for so that the group kill ends it at once.
(
  trap - INT TERM HUP EXIT
  while :; do
    sample
    sleep "$INTERVAL" &
    wait $!
  done
) &
sampler=$!

# the command: standard input closed (see the header). If it does not exist the shell says so on the standard error and its status is 127.
"$@" </dev/null &
child=$!

# Wait for it. A signal with a trap interrupts `wait` (the status is then above 128 and the command is still there), so the wait is repeated until the command
# is gone; the last `wait` gives its real exit status. The command can be a zombie for a moment, which `kill -0` still counts as there: one more `wait` reaps it.
status=0
while kill -0 "$child" 2>/dev/null; do
  wait "$child"
  status=$?
done
ENDED=$(now_s)
set +m

stop_sampler
sample   # the last line: the state of the machine just after the command ended

# ------------------------------------------------------------------ the summary
seconds=$(awk -v a="$ENDED" -v s="$START" 'BEGIN { printf "%.1f", a - s }')
# From the CSV, so that what is reported is exactly what was written: the peak of a column, or "not available" if no line held a number in it.
peak() { awk -F, -v col="$1" -v na="$NA" -v mode="$2" 'NR > 1 && $col ~ /^[0-9]+$/ { if (!seen || (mode == "max" ? $col > best : $col < best)) best = $col; seen = 1 } END { if (seen) printf "%d MiB", best; else printf "%s", na }' "$CSV"; }
samples=$(awk 'END { print NR - 1 }' "$CSV")
how="exited with status $status"
case $status in
  130) how="was stopped by Ctrl-C (status 130)" ;;
  143) how="was stopped by SIGTERM (status 143)" ;;
  127) how="could not be run: the command was not found (status 127)" ;;
  126) how="could not be run: it is not executable (status 126)" ;;
esac
printf '%s: "%s" ran for %s seconds and %s. Peak memory used on the machine: %s. Lowest MemAvailable: %s. Peak GPU memory used (nvidia-smi): %s. %s sample(s), one every %s s, are in %s.\n' \
  "$PROG" "$*" "$seconds" "$how" "$(peak 3 max)" "$(peak 4 min)" "$(peak 5 max)" "$samples" "$INTERVAL" "$CSV" >&2
[[ -z $stopped ]] || printf '%s: the %s signal was passed on to the command.\n' "$PROG" "$stopped" >&2

exit "$status"
