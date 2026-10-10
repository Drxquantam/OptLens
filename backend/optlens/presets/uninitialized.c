#include <stdio.h>

/* Leaves a recognisable value in the stack slot that `pick` reuses at -O0. */
__attribute__((noinline)) void scribble(void) {
    volatile int junk = 1337;
    (void)junk;
}

/* When flag == 0, `value` is never assigned: reading it is undefined.
 * Unoptimised code returns whatever is lying on the stack; optimised code may
 * assume the "assigned" path is the only possible one and return 42. */
__attribute__((noinline)) int pick(int flag) {
    int value;
    if (flag)
        value = 42;
    return value;
}

int main(void) {
    volatile int flag = 0;
    scribble();
    printf("value = %d\n", pick(flag));
    return 0;
}
