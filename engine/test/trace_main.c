/* Desktop harness for the loader and the script VM.
 *
 * It replays recorded decisions (menu picks, explore trigger picks) so that its trace can be
 * compared with the Python interpreters (script/tools/memo/ctrace.py drives it):
 *
 *   memo_trace <memo.dat> --inspect [--crc N]        dump header, tables, code and strings
 *   memo_trace <memo.dat> --stream ID [--stream ..]  stream blocks through the chunked reader
 *   memo_trace <memo.dat> --decisions F [--text]     run the game once per recorded play
 *
 * Output lines are described in ctrace.py (format_event / run line). Not part of the Zeal build. */
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "memo_dat.h"
#include "memo_host.h"
#include "memo_vm.h"

#ifndef MEMO_TRACE_VARS
#error "build the harness with -DMEMO_TRACE_VARS (the VM must call host_var)"
#endif

static int text_mode;
static unsigned long event_count;
static uint32_t crc_state;
static uint32_t crc_table[256];

static unsigned *dec_n, *dec_pick;
static size_t dec_count, dec_pos;
static long run_id;

static void crc_init(void)
{
    uint32_t i, k, c;

    for (i = 0; i < 256; i++) {
        c = i;
        for (k = 0; k < 8; k++) {
            c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        }
        crc_table[i] = c;
    }
}

static uint32_t crc_update(uint32_t crc, const void *data, size_t n)
{
    const uint8_t *p = data;

    crc = ~crc;
    while (n--) {
        crc = crc_table[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    }
    return ~crc;
}

static const char *esc(const char *s)
{
    static char out[1024];
    size_t o = 0;

    for (; *s && o < sizeof out - 3; s++) {
        if (*s == '\n') {
            out[o++] = '\\';
            out[o++] = 'n';
        } else if (*s == '\\') {
            out[o++] = '\\';
            out[o++] = '\\';
        } else {
            out[o++] = *s;
        }
    }
    out[o] = '\0';
    return out;
}

static void emit(const char *fmt, ...)
{
    char line[1200];
    va_list ap;
    int n;

    va_start(ap, fmt);
    n = vsnprintf(line, sizeof line - 1, fmt, ap);
    va_end(ap);
    line[n++] = '\n';
    crc_state = crc_update(crc_state, line, (size_t)n);
    event_count++;
    if (text_mode) {
        fwrite(line, 1, (size_t)n, stdout);
    }
}

static unsigned take(unsigned n, const char *what)
{
    if (dec_pos >= dec_count) {
        fprintf(stderr, "run %ld: decision log exhausted at a %s (n=%u)\n", run_id, what, n);
        exit(3);
    }
    if (dec_n[dec_pos] != n) {
        fprintf(stderr, "run %ld: decision %zu is for n=%u but the VM offers n=%u at a %s\n",
                run_id, dec_pos, dec_n[dec_pos], n, what);
        exit(3);
    }
    return dec_pick[dec_pos++];
}

void host_say(uint8_t who, uint8_t expr, uint8_t style, const char *text)
{
    emit("say %u %u %u %s", who, expr, style, esc(text));
}
void host_map(uint8_t map, uint8_t spawn, uint8_t t) { emit("map %u %u %u", map, spawn, t); }
void host_fade(uint8_t mode, uint8_t t) { emit("fade %u %u", mode, t); }
void host_music(uint8_t id) { emit("music %u", id); }
void host_sfx(uint8_t id) { emit("sfx %u", id); }
void host_cg(uint8_t id) { emit("cg %u", id); }
void host_cg_off(void) { emit("cg_off"); }
void host_tutorial(uint8_t id, const char *text) { emit("tutorial %u %s", id, esc(text)); }
void host_wait(uint8_t ticks) { emit("wait %u", ticks); }
void host_end(void) { emit("end"); }
void host_var(uint8_t idx, uint8_t value) { emit("var %u %u", idx, value); }

uint8_t host_choose(const char *prompt, const char *const *options, uint8_t n)
{
    unsigned pick = take(n, "menu");

    (void)prompt;
    (void)options;
    emit("choice %u %u", n, pick);
    return (uint8_t)pick;
}

uint8_t host_pick_trigger(uint8_t objective, const uint8_t *table_idx, const uint8_t *trig_id, uint8_t n)
{
    unsigned k = take(n, "trigger pick");

    (void)objective;
    (void)trig_id;
    if (k < n) {
        emit("trigger %u", table_idx[k]);
    }
    return (uint8_t)k;
}

/* ------------------------------------------------------------------ inspect */

static int inspect(void)
{
    DatEntry e;
    uint16_t i, id, vals[3];
    uint8_t n, t, k, w, count, vmax[MEMO_VAR_MAX], vinit[MEMO_VAR_MAX];
    uint16_t s;

    printf("meta scenes %u crc %08lX entries %u\n", dat_scene_count, (unsigned long)dat_crc, dat_entry_count());
    for (id = 0; id < dat_entry_count(); id++) {
        if (!dat_entry(id, &e)) {
            printf("entry %u unreadable\n", id);
            return 1;
        }
        printf("entry %u %lu %u %u %u\n", id, (unsigned long)e.offset, e.size, e.type, e.flags);
    }
    if (!dat_load_vars(vmax, vinit, MEMO_VAR_MAX, &count)) {
        printf("vars unreadable\n");
        return 1;
    }
    printf("vars %u\n", count);
    for (i = 0; i < count; i++) {
        printf("var %u %u %u\n", i, vmax[i], vinit[i]);
    }
    for (t = 0; t < DAT_TABLE_COUNT; t++) {
        count = dat_index_count(t);
        w = dat_index_width(t);
        printf("table %u %u\n", t, count);
        for (n = 0; n < count; n++) {
            if (!dat_index_get(t, n, vals)) {
                printf("index %u %u unreadable\n", t, n);
                return 1;
            }
            printf("index %u %u", t, n);
            for (k = 0; k < w; k++) {
                printf(" %u", vals[k]);
            }
            printf("\n");
        }
    }
    for (n = 1; n <= dat_scene_count; n++) {
        char buf[MEMO_DIALOG_MAX];
        uint8_t rc = dat_load_scene(n);

        if (rc != DAT_OK) {
            printf("scene %u error %u\n", n, rc);
            return 1;
        }
        printf("scene %u entry %u size %u crc %08lX\n", n, dat_code_entry, dat_code_size,
               (unsigned long)crc_update(0, dat_code, dat_code_size));
        for (s = 0;; s++) {
            if (!dat_load_string(s, buf, sizeof buf)) {
                break;
            }
            printf("str %u %u %s\n", n, s, esc(buf));
        }
    }
    return 0;
}

/* ---------------------------------------------------------------------- run */

static uint32_t stream_crc;
static unsigned long stream_bytes;

static bool stream_sink(const uint8_t *data, uint16_t n, void *ctx)
{
    (void)ctx;
    stream_crc = crc_update(stream_crc, data, n);
    stream_bytes += n;
    return true;
}

/* Stream a block in odd sized chunks and report what arrived. */
static void stream(unsigned id)
{
    uint8_t buf[1000];

    stream_crc = 0;
    stream_bytes = 0;
    if (dat_stream_block((uint16_t)id, buf, sizeof buf, stream_sink, NULL)) {
        printf("stream %u bytes %lu crc %08lX\n", id, stream_bytes, (unsigned long)stream_crc);
    } else {
        printf("stream %u error\n", id);
    }
}

static int load_decisions(const char *path, FILE **out)
{
    *out = fopen(path, "r");
    return *out != NULL;
}

static int next_run(FILE *f)
{
    size_t i;
    char tag[4];

    if (fscanf(f, " %3s %ld %zu", tag, &run_id, &dec_count) != 3 || strcmp(tag, "R") != 0) {
        return 0;
    }
    dec_n = realloc(dec_n, (dec_count + 1) * sizeof *dec_n);
    dec_pick = realloc(dec_pick, (dec_count + 1) * sizeof *dec_pick);
    for (i = 0; i < dec_count; i++) {
        if (fscanf(f, "%u %u", &dec_n[i], &dec_pick[i]) != 2) {
            return 0;
        }
    }
    dec_pos = 0;
    return 1;
}

int main(int argc, char **argv)
{
    const char *path = NULL, *decisions = NULL;
    uint32_t expect_crc = 0;
    int do_inspect = 0, i;
    unsigned streams[256], nstreams = 0;
    uint8_t rc;
    FILE *f;

    memo_tutorial_once = false;   /* the traces list every tutorial op, as the Python interpreters do */
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--inspect")) {
            do_inspect = 1;
        } else if (!strcmp(argv[i], "--stream") && i + 1 < argc && nstreams < 256) {
            streams[nstreams++] = (unsigned)strtoul(argv[++i], NULL, 0);
        } else if (!strcmp(argv[i], "--text")) {
            text_mode = 1;
        } else if (!strcmp(argv[i], "--decisions") && i + 1 < argc) {
            decisions = argv[++i];
        } else if (!strcmp(argv[i], "--crc") && i + 1 < argc) {
            expect_crc = (uint32_t)strtoul(argv[++i], NULL, 0);
        } else if (!strcmp(argv[i], "--tutorial-once")) {
            memo_tutorial_once = true;
        } else if (argv[i][0] != '-' && !path) {
            path = argv[i];
        } else {
            fprintf(stderr, "bad argument %s\n", argv[i]);
            return 2;
        }
    }
    if (!path) {
        fprintf(stderr, "usage: memo_trace memo.dat (--inspect | --decisions file [--text]) [--crc N]\n");
        return 2;
    }
    crc_init();

    rc = dat_open(path, expect_crc);
    if (rc != DAT_OK) {
        printf("open error %u\n", rc);
        return 1;
    }
    if (do_inspect) {
        return inspect();
    }
    if (nstreams) {
        for (i = 0; i < (int)nstreams; i++) {
            stream(streams[i]);
        }
        return 0;
    }
    if (!decisions || !load_decisions(decisions, &f)) {
        fprintf(stderr, "need --decisions with a readable file\n");
        return 2;
    }
    while (next_run(f)) {
        uint8_t j;

        crc_state = 0;
        event_count = 0;
        rc = memo_vm_init();
        if (rc == MEMO_OK) {
            rc = memo_run_game();
        }
        printf("RUN %ld events %lu crc %08lX rc %u scene %u pc %u vars", run_id, event_count,
               (unsigned long)crc_state, rc, memo_fault_scene, memo_fault_pc);
        for (j = 0; j < memo_var_count; j++) {
            printf(" %u", memo_vars[j]);
        }
        printf("\n");
        if (rc == MEMO_OK && dec_pos != dec_count) {
            printf("LEFTOVER %ld %zu\n", run_id, dec_count - dec_pos);
        }
    }
    fclose(f);
    return 0;
}
