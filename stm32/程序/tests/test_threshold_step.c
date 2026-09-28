#include <assert.h>
#include "threshold_step.h"

int main(void)
{
    assert(Threshold_Down8(0u) == 0u);
    assert(Threshold_Down8(1u) == 0u);
    assert(Threshold_Up8(99u) == 100u);
    assert(Threshold_Up8(100u) == 100u);
    assert(Threshold_Up8(255u) == 100u);

    assert(Threshold_Down16(0u) == 0u);
    assert(Threshold_Down16(9u) == 0u);
    assert(Threshold_Down16(10u) == 0u);
    assert(Threshold_Down16(11u) == 1u);
    assert(Threshold_Up16(1989u) == 1999u);
    assert(Threshold_Up16(1990u) == 2000u);
    assert(Threshold_Up16(2000u) == 2000u);
    assert(Threshold_Up16(65535u) == 2000u);
    return 0;
}
