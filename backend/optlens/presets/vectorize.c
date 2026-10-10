#include <stdio.h>

#define N 1024

/* A simple, dependence-free loop: a textbook candidate for the loop vectorizer.
 * Compare -O0 (one element per iteration) with -O3 (SIMD registers, several
 * elements per instruction) in the Assembly Diff tab. */
float a[N], b[N], c[N];

__attribute__((noinline)) void saxpy(float k) {
    for (int i = 0; i < N; i++)
        c[i] = k * a[i] + b[i];
}

int main(void) {
    for (int i = 0; i < N; i++) {
        a[i] = (float)i;
        b[i] = (float)(N - i);
    }
    saxpy(2.0f);
    double checksum = 0;
    for (int i = 0; i < N; i++)
        checksum += c[i];
    printf("checksum = %.1f\n", checksum);
    return 0;
}
