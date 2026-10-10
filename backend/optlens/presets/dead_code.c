#include <stdio.h>

/* Work whose result is never observed is removed entirely at -O2/-O3.
 * `unused` is computed in a loop but never printed, and the branch on
 * DEBUG is provably false, so neither survives in the optimised assembly. */
#define DEBUG 0

static int expensive(int n) {
    int acc = 0;
    for (int i = 0; i < n; i++)
        acc ^= i * 2654435761u;
    return acc;
}

int main(void) {
    int unused = expensive(1000000); /* dead: value never used */
    (void)unused;
    if (DEBUG)
        printf("debug: %d\n", expensive(42));
    puts("done");
    return 0;
}
