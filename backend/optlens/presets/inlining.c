#include <stdio.h>

/* Small helpers like these are inlined at -O2/-O3: the calls disappear and the
 * arithmetic is merged into the caller. The Remarks tab shows Clang's
 * "inlined into" decisions with their cost model numbers. */
static int square(int x) { return x * x; }
static int add(int a, int b) { return a + b; }

static int dist2(int x1, int y1, int x2, int y2) {
    return add(square(x2 - x1), square(y2 - y1));
}

int main(void) {
    int total = 0;
    for (int i = 0; i < 10; i++)
        total += dist2(i, 2 * i, 3 * i, i + 7);
    printf("total = %d\n", total);
    return 0;
}
