#include <stdio.h>

/* Summing 0..n-1 in a loop. Clang's scalar-evolution analysis recognises the
 * pattern and replaces the whole loop with the closed form n*(n-1)/2, so the
 * -O3 assembly has no loop at all, just a few multiplies and shifts. */
__attribute__((noinline)) unsigned long long triangle(unsigned long long n) {
    unsigned long long sum = 0;
    for (unsigned long long i = 0; i < n; i++)
        sum += i;
    return sum;
}

int main(void) {
    volatile unsigned long long n = 100000;
    printf("sum(0..%llu) = %llu\n", n - 1, triangle(n));
    return 0;
}
