#include <limits.h>
#include <stdio.h>

/* "x + 1 > x" is always true for mathematical integers. In C, signed overflow
 * is undefined behaviour, so the optimizer may assume it never happens and
 * fold the whole comparison to 1. GCC folds it even at -O0; Clang -O0 really
 * performs the wrapping addition and gets 0. */
__attribute__((noinline)) int always_bigger(int x) {
    return x + 1 > x;
}

int main(void) {
    volatile int big = INT_MAX; /* volatile: hide the value from the optimizer */
    int x = big;
    printf("INT_MAX + 1 > INT_MAX ? %d\n", always_bigger(x));
    return 0;
}
