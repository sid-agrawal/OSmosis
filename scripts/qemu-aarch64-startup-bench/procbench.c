/* procbench: measure process creation (fork + execve of a trivial static binary).
 *
 * Reports per-iteration wall-clock (CLOCK_MONOTONIC) for fork+exec+wait, plus
 * mean/median/stddev in milliseconds. Run inside the guest whose process
 * creation you want to characterise.
 *
 * Build (static, aarch64):  aarch64-linux-gnu-gcc -O2 -static -o procbench procbench.c
 * Usage:  ./procbench <iterations> </path/to/trivial-static-binary>
 *
 * The child binary should do as little as possible (e.g. `int main(){return 0;}`
 * built static) so the measurement reflects process-creation cost, not payload.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <time.h>

static double sqrt_(double x); /* tiny sqrt, defined below (avoids -lm) */

static int cmp_double(const void *a, const void *b) {
    double da = *(const double *)a, db = *(const double *)b;
    return (da > db) - (da < db);
}

int main(int argc, char **argv) {
    int n = (argc > 1) ? atoi(argv[1]) : 200;
    const char *child = (argc > 2) ? argv[2] : "./trivial";
    if (n < 1) n = 1;

    double *ms = calloc(n, sizeof(double));
    char *const cargv[] = { (char *)child, NULL };
    char *const cenv[]  = { NULL };

    /* warm up caches: one throwaway run */
    { pid_t p = fork(); if (p == 0) { execve(child, cargv, cenv); _exit(127); } if (p > 0) waitpid(p, NULL, 0); }

    for (int i = 0; i < n; i++) {
        struct timespec t0, t1;
        clock_gettime(CLOCK_MONOTONIC, &t0);
        pid_t pid = fork();
        if (pid == 0) {
            execve(child, cargv, cenv);
            _exit(127);
        } else if (pid > 0) {
            int st;
            waitpid(pid, &st, 0);
            clock_gettime(CLOCK_MONOTONIC, &t1);
            ms[i] = (t1.tv_sec - t0.tv_sec) * 1e3 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
        } else {
            perror("fork");
            return 1;
        }
    }

    double sum = 0, sum2 = 0;
    for (int i = 0; i < n; i++) { sum += ms[i]; sum2 += ms[i] * ms[i]; }
    double mean = sum / n;
    double var = sum2 / n - mean * mean;
    double sd = var > 0 ? sqrt_(var) : 0;

    qsort(ms, n, sizeof(double), cmp_double);
    double median = (n & 1) ? ms[n/2] : (ms[n/2 - 1] + ms[n/2]) / 2.0;

    printf("iterations=%d child=%s\n", n, child);
    printf("mean_ms=%.4f median_ms=%.4f stddev_ms=%.4f min_ms=%.4f max_ms=%.4f\n",
           mean, median, sd, ms[0], ms[n-1]);
    /* also dump raw for CSV capture */
    for (int i = 0; i < n; i++) printf("RAW %.6f\n", ms[i]);
    free(ms);
    return 0;
}

/* tiny sqrt to avoid -lm when static-linking on minimal toolchains */
static double sqrt_(double x) {
    if (x <= 0) return 0;
    double g = x;
    for (int i = 0; i < 60; i++) g = 0.5 * (g + x / g);
    return g;
}
