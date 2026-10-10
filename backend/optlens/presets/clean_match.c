#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* A well-defined program: unsigned arithmetic (wraps by definition), bounded
 * loops, initialised data, no pointer tricks. Every compiler and optimisation
 * level must print exactly the same thing, and the sanitizers stay quiet. */
static uint32_t fnv1a(const char *s) {
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < strlen(s); i++) {
        h ^= (uint8_t)s[i];
        h *= 16777619u;
    }
    return h;
}

static int collatz_steps(uint64_t n) {
    int steps = 0;
    while (n != 1) {
        n = (n % 2 == 0) ? n / 2 : 3 * n + 1;
        steps++;
    }
    return steps;
}

int main(void) {
    char line[256] = "";
    if (fgets(line, sizeof line, stdin) == NULL)
        strcpy(line, "optlens"); /* no input: use a default word */
    line[strcspn(line, "\n")] = '\0';
    printf("fnv1a(\"%s\") = %08x\n", line, fnv1a(line));

    int best = 0;
    uint64_t arg = 1;
    for (uint64_t n = 1; n < 10000; n++) {
        int s = collatz_steps(n);
        if (s > best) {
            best = s;
            arg = n;
        }
    }
    printf("longest Collatz chain below 10000: %llu (%d steps)\n", (unsigned long long)arg, best);
    return 0;
}
