#include <assert.h>
#include <stdio.h>
#include "../HARDWARE/key_events.h"

static void test_fifo_and_processing_overlap(void)
{
    KeyEventQueue queue = {{0}, 0};
    unsigned char current;
    assert(KeyEvent_Take(&queue) == 0);
    assert(KeyEvent_Push(&queue, 1) == 1);
    assert(KeyEvent_Push(&queue, 2) == 1);
    current = KeyEvent_Take(&queue);
    assert(current == 1);
    /* An IRQ during handling must survive clearing the local event. */
    assert(KeyEvent_Push(&queue, 3) == 1);
    current = 0;
    assert(current == 0);
    assert(KeyEvent_Take(&queue) == 2);
    assert(KeyEvent_Take(&queue) == 3);
    assert(KeyEvent_Take(&queue) == 0);
}

static void test_full_queue_and_network_event(void)
{
    KeyEventQueue queue = {{0}, 0};
    unsigned char i;
    for (i = 0; i < KEY_EVENT_CAPACITY; ++i)
        assert(KeyEvent_Push(&queue, (unsigned char)(i % 4 + 1)) == 1);
    assert(KeyEvent_Push(&queue, 2) == 0);
    assert(KeyEvent_Push(&queue, 44) == 1);
    assert(KeyEvent_Push(&queue, 44) == 1);
    assert(KeyEvent_Push(&queue, 4) == 0);
    for (i = 1; i < KEY_EVENT_CAPACITY; ++i)
        assert(KeyEvent_Take(&queue) == (unsigned char)(i % 4 + 1));
    assert(KeyEvent_Take(&queue) == 44);
    assert(KeyEvent_Take(&queue) == 0);
}

static void test_repeat_cycles_and_all_event_codes(void)
{
    KeyEventQueue queue = {{0}, 0};
    const unsigned char events[] = {1, 2, 3, 4, 11, 22, 33, 44};
    unsigned int cycle;
    unsigned char i;
    for (cycle = 0; cycle < 1000; ++cycle)
    {
        for (i = 0; i < KEY_EVENT_CAPACITY; ++i)
            assert(KeyEvent_Push(&queue, events[i]) == 1);
        for (i = 0; i < KEY_EVENT_CAPACITY; ++i)
            assert(KeyEvent_Take(&queue) == events[i]);
        assert(KeyEvent_Take(&queue) == 0);
    }
}

int main(void)
{
    test_fifo_and_processing_overlap();
    test_full_queue_and_network_event();
    test_repeat_cycles_and_all_event_codes();
    puts("key event tests passed");
    return 0;
}
