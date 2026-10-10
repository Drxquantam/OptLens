#include <stdio.h>

/* Classic off-by-one: the loop reads table[4], one element past the end.
 * The optimizer is allowed to assume that never happens; at -O0 the program
 * reads whatever sits next to the array on the stack. AddressSanitizer
 * reports a stack-buffer-overflow at the exact line. */
__attribute__((noinline)) int sum(const int *table, int n) {
    int total = 0;
    for (int i = 0; i <= n; i++) /* bug: should be i < n */
        total += table[i];
    return total;
}

int main(void) {
    volatile int guard = 1000;
    int table[4] = {1, 2, 3, 4};
    volatile int n = 4;
    printf("sum = %d (guard %d)\n", sum(table, n), guard);
    return 0;
}
