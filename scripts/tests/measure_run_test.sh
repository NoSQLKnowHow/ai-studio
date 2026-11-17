#!/usr/bin/env bash
# Tests for scripts/measure_run.sh:   bash scripts/tests/measure_run_test.sh
# (FAILFAST=1 stops at the first failure.)
#
# Everything runs in a throw-away folder, with the same small harness as scripts/tests/backup_restore_test.sh (ok, bad, check, contains, equals,
# section, a PASS/FAIL count and a non-zero exit if anything failed). The commands that are measured are real (`sleep`, `bash -c 'exit 7'`); the
# things that differ between machines are replaced by stand-ins the test controls: `nvidia-smi` (a stub that prints what the test wants, or is absent
# altogether) and /proc/meminfo (a file named by MEASURE_RUN_MEMINFO, the script's test seam). So this proves the script's own logic: the CSV, the
# summary, the exit status that is passed through, the refusals, and that Ctrl-C leaves no process behind. It does not prove what a real GPU's
# nvidia-smi prints on a DGX Spark: that is one of the things the experiment itself shows (docs/SPARK_TEST.md section 37).
set -uo pipefail

SRC=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT="$SRC/scripts/measure_run.sh"
T=$(mktemp -d)
# the folder goes away on any exit, and so does anything the tests started and left running (a test that failed half way must not leave a `sleep` behind)
cleanup() { pkill -f 'sleep 31\.7' 2>/dev/null; rm -rf -- "$T"; }
trap cleanup EXIT
PASS=0; FAIL=0

# ------------------------------------------------------------------ helpers (the same as backup_restore_test.sh)
ok()   { PASS=$((PASS + 1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$1"; [[ -n ${2:-} ]] && printf '        %s\n' "$2"; [[ -z ${FAILFAST:-} ]] || exit 1; }
check() { local desc=$1; shift; if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi; }
contains() { local desc=$1 text=$2 needle=$3
  if [[ $text == *"$needle"* ]]; then ok "$desc"; else bad "$desc" "wanted: $needle | got: ${text:0:400}"; fi; }
equals() { local desc=$1 got=$2 want=$3
  if [[ $got == "$want" ]]; then ok "$desc"; else bad "$desc" "wanted: $want | got: $got"; fi; }
section() { printf '\n%s\n' "$1"; }

# ------------------------------------------------------------------ the stand-ins
# A PATH that holds only the programs the script needs (symlinks to the real ones) and no nvidia-smi, so that "nvidia-smi absent" is true whatever
# machine this test runs on (on a Spark the real one exists and would otherwise be found).
BARE="$T/bare"; mkdir -p "$BARE"
for tool in bash sleep date awk sed cat timeout mkdir rm dirname; do
  found=$(command -v "$tool" 2>/dev/null) && [[ -x $found ]] && ln -s "$found" "$BARE/$tool"
done
# A folder with a stub nvidia-smi, put in front of the bare PATH when a test wants the GPU to be there. What it prints is chosen by STUB_SMI_OUT
# (it prints the text as it is, so "100\n200" is two GPUs) and it fails with STUB_SMI_FAIL set.
WITH="$T/with"; mkdir -p "$WITH"
cat > "$WITH/nvidia-smi" <<'STUB'
#!/usr/bin/env bash
[[ -n ${STUB_SMI_FAIL:-} ]] && { echo "NVIDIA-SMI has failed" >&2; exit 9; }
printf '%b\n' "${STUB_SMI_OUT:-0}"
STUB
chmod +x "$WITH/nvidia-smi"

# mm RESULT_VAR ARGS...: run measure_run.sh on the bare PATH (no nvidia-smi) and keep what it printed. It sets $OUT (the standard output), $ERR (the
# standard error, where the summary goes), $RC (the exit status) and writes the CSV to $T/m.csv. Extra environment goes before the call: `env X=1 mm ...`.
mm() {
  rm -f "$T/m.csv"
  OUT=$(PATH="$BARE" bash "$SCRIPT" -o "$T/m.csv" "$@" 2>"$T/err.txt"); RC=$?
  ERR=$(cat "$T/err.txt")
}
# mm_smi: the same, with the stub nvidia-smi on the PATH.
mm_smi() {
  rm -f "$T/m.csv"
  OUT=$(PATH="$WITH:$BARE" bash "$SCRIPT" -o "$T/m.csv" "$@" 2>"$T/err.txt"); RC=$?
  ERR=$(cat "$T/err.txt")
}
rows() { awk 'END { print NR - 1 }' "$T/m.csv"; }          # the number of samples (the CSV minus its header line)
column() { awk -F, -v c="$1" 'NR > 1 { print $c }' "$T/m.csv" | sort -u | tr '\n' ' '; }   # the distinct values of one column, to compare as text

# ------------------------------------------------------------------ 1. a command that works
section "a command that succeeds: sleep 1"
mm -- sleep 1
equals "exit status 0 is passed through" "$RC" 0
equals "the CSV has the header line first" "$(head -n 1 "$T/m.csv")" "utc_time,elapsed_s,mem_used_mib,mem_available_mib,gpu_mem_used_mib"
check "it has at least two samples (one at the start, one at the end), though the command is shorter than the 2 s interval" test "$(rows)" -ge 2
check "every sample has five fields" bash -c "awk -F, 'NR > 1 && NF != 5 { exit 1 }' '$T/m.csv'"
check "the elapsed seconds start at 0 and end at about 1 (between 0.9 and 3)" \
  bash -c "awk -F, 'NR == 2 { a = \$2 } END { exit !(a == 0 && \$2 >= 0.9 && \$2 <= 3) }' '$T/m.csv'"
contains "the summary says how long it ran" "$ERR" 'ran for 1.'
contains "the summary says the status" "$ERR" "exited with status 0"
contains "the summary names the CSV" "$ERR" "$T/m.csv"
check "the memory columns are numbers on this machine (it has /proc/meminfo)" bash -c "awk -F, 'NR > 1 && (\$3 !~ /^[0-9]+\$/ || \$4 !~ /^[0-9]+\$/) { exit 1 }' '$T/m.csv'"

section "the command's own output stays on the standard output, the summary on the standard error"
# shellcheck disable=SC2016  # the $1 is meant for the inner bash, so the quotes are single on purpose
mm -- bash -c 'echo "from the command: $1"' _ "two words"
equals "the command's words are on stdout, and arguments with a space arrive whole" "$OUT" "from the command: two words"
contains "the summary is not on stdout's side" "$ERR" "measure_run:"
check "and nothing of the summary is in stdout" bash -c "[[ '$OUT' != *measure_run* ]]"

# ------------------------------------------------------------------ 2. the exit status
section "a command that fails: its exit status is passed through"
mm -- bash -c 'exit 7'
equals "exit 7 comes out as 7" "$RC" 7
contains "the summary says 7" "$ERR" "exited with status 7"
check "the CSV is still written (a failed run is data too)" test "$(rows)" -ge 1

section "a command that does not exist"
mm -- this_command_does_not_exist_v127
equals "the status is 127 (the shell's own)" "$RC" 127
contains "the summary says it was not found" "$ERR" "the command was not found (status 127)"
check "the script itself did not crash: the CSV exists and has samples" test "$(rows)" -ge 1

# ------------------------------------------------------------------ 3. the sources
section "nvidia-smi absent: the GPU is 'not available', never a number"
mm -i 0.2 -- sleep 1
equals "every sample's GPU field says so" "$(column 5)" "not available "
contains "the summary says so" "$ERR" "Peak GPU memory used (nvidia-smi): not available"
check "and the memory of the machine was still measured" bash -c "awk -F, 'NR > 1 && \$3 !~ /^[0-9]+\$/ { exit 1 }' '$T/m.csv'"
check "-i 0.2 gave several samples for a one second command (a decimal interval works)" test "$(rows)" -ge 4

section "nvidia-smi present: its number is recorded, two GPUs are added up"
STUB_SMI_OUT=2048 mm_smi -i 0.3 -- sleep 1
equals "one GPU: 2048 in every sample" "$(column 5)" "2048 "
contains "the summary reports the peak" "$ERR" "Peak GPU memory used (nvidia-smi): 2048 MiB"
STUB_SMI_OUT='100\n200' mm_smi -- sleep 1
equals "two GPUs (two lines) are summed: 300" "$(column 5)" "300 "

section "nvidia-smi that cannot say: '[N/A]' or a failure is 'not available', not a guess and not 0"
STUB_SMI_OUT='[N/A]' mm_smi -- sleep 1
equals "a line that is not a number" "$(column 5)" "not available "
STUB_SMI_FAIL=1 mm_smi -- sleep 1
equals "a failing nvidia-smi" "$(column 5)" "not available "
STUB_SMI_OUT='100\n[N/A]' mm_smi -- sleep 1
equals "one GPU's number and another's [N/A] is not a sum of the part that was known" "$(column 5)" "not available "
contains "and the summary says so" "$ERR" "Peak GPU memory used (nvidia-smi): not available"

section "memory: the numbers come from /proc/meminfo, and a missing file is 'not available'"
printf 'MemTotal:        2097152 kB\nMemFree:          100000 kB\nMemAvailable:    1048576 kB\n' > "$T/meminfo"
MEASURE_RUN_MEMINFO="$T/meminfo" mm -- sleep 1
equals "used = MemTotal - MemAvailable = 1024 MiB, available = 1024 MiB" "$(column 3)/$(column 4)" "1024 /1024 "
contains "the summary names both" "$ERR" "Peak memory used on the machine: 1024 MiB. Lowest MemAvailable: 1024 MiB."
MEASURE_RUN_MEMINFO="$T/does-not-exist" mm -- sleep 1
equals "no meminfo: used says not available" "$(column 3)" "not available "
equals "no meminfo: available says not available" "$(column 4)" "not available "
contains "no meminfo: the summary says not available for both" "$ERR" "Peak memory used on the machine: not available. Lowest MemAvailable: not available."
printf 'MemTotal:        2097152 kB\n' > "$T/meminfo-no-avail"
MEASURE_RUN_MEMINFO="$T/meminfo-no-avail" mm -- sleep 1
equals "a meminfo without a MemAvailable line (an old kernel) is 'not available', not a guess" "$(column 4)" "not available "

# ------------------------------------------------------------------ 4. mistakes in the call
section "mistakes in how it is called give 64 and start nothing"
mm
equals "no command at all: 64" "$RC" 64
contains "and it says what to do" "$ERR" "no command given"
mm -i abc -- sleep 1
equals "an interval that is not a number: 64" "$RC" 64
mm -i 0 -- sleep 1
equals "an interval of 0 (it would sample in a tight loop): 64" "$RC" 64
mm -i -3 -- sleep 1
equals "a negative interval: 64" "$RC" 64
mm sleep 1
equals "a command without the -- before it: 64" "$RC" 64
OUT=$(PATH="$BARE" bash "$SCRIPT" -o "$T/no/such/folder/m.csv" -- sleep 1 2>&1); RC=$?
equals "a CSV path that cannot be written is found out before the command runs: 64" "$RC" 64
contains "and says so" "$OUT" "cannot write to"
OUT=$(PATH="$BARE" bash "$SCRIPT" --help 2>&1); RC=$?
equals "--help exits 0" "$RC" 0
contains "and prints the usage" "$OUT" "scripts/measure_run.sh [-i SECONDS]"

# ------------------------------------------------------------------ 5. Ctrl-C and the sampler's clean-up
# A real Ctrl-C reaches the foreground process group of a terminal. `set -m` here gives the script a process group of its own, like a foreground job, and
# `kill -INT -- -PID` is then what the terminal does. (A plain `&` in a script would start it with Ctrl-C switched off, which is why job control is on.)
# The command is `sleep 31.7`, a duration nothing else uses, so that a leftover can be found by name.
section "Ctrl-C: passed to the command, the sampler stopped, the summary printed, nothing left behind"
set -m
bash "$SCRIPT" -i 0.3 -o "$T/c.csv" -- sleep 31.7 > "$T/c.out" 2> "$T/c.err" &
PID=$!
set +m
sleep 1.5                                    # long enough for several samples
kill -INT -- "-$PID"                         # what the terminal does
wait "$PID"; RC=$?
equals "exit status 130 (the command was stopped by SIGINT)" "$RC" 130
contains "the summary says it was stopped by Ctrl-C" "$(cat "$T/c.err")" "was stopped by Ctrl-C (status 130)"
check "the command is gone" bash -c "! pgrep -f 'sleep 31\.7' >/dev/null"
SIZE_NOW=$(wc -l < "$T/c.csv"); sleep 1
equals "the sampler is gone too: the CSV did not grow in the second after" "$(wc -l < "$T/c.csv")" "$SIZE_NOW"
check "and the samples taken before the interrupt are in the CSV" test "$SIZE_NOW" -ge 4

section "SIGTERM sent to the script alone is passed on, with the same clean-up"
bash "$SCRIPT" -i 0.3 -o "$T/t.csv" -- sleep 31.7 > "$T/t.out" 2> "$T/t.err" &
PID=$!
sleep 1.2
kill -TERM "$PID"                            # only the script, not the command: the script must pass it on
wait "$PID"; RC=$?
equals "exit status 143" "$RC" 143
check "the command is gone" bash -c "! pgrep -f 'sleep 31\.7' >/dev/null"
SIZE_NOW=$(wc -l < "$T/t.csv"); sleep 0.8
equals "the sampler stopped" "$(wc -l < "$T/t.csv")" "$SIZE_NOW"

section "after a normal run the sampler is gone as well"
mm -i 0.2 -- sleep 0.6
SIZE_NOW=$(wc -l < "$T/m.csv"); sleep 0.8
equals "the CSV does not grow after the script has returned" "$(wc -l < "$T/m.csv")" "$SIZE_NOW"
# the [m] keeps this check's own command line from matching the pattern it looks for
check "no sampler process is left, nor a script still running" bash -c "! pgrep -f '[m]easure_run.sh -i 0.2' >/dev/null"

# ================================================================== result
printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
(( FAIL == 0 ))
