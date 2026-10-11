#ifndef KEY_EVENTS_H
#define KEY_EVENTS_H

#define KEY_EVENT_CAPACITY 8u
#define KEY_EVENT_NETWORK_CONFIG 44u

typedef struct
{
    unsigned char events[KEY_EVENT_CAPACITY];
    unsigned char count;
} KeyEventQueue;

/* Caller serializes IRQ producer and foreground consumer. */
static unsigned char KeyEvent_Take(volatile KeyEventQueue *queue)
{
    unsigned char event;
    unsigned char i;
    if (queue->count == 0u)
        return 0u;
    event = queue->events[0];
    for (i = 1u; i < queue->count; ++i)
        queue->events[i - 1u] = queue->events[i];
    --queue->count;
    return event;
}

/* Full queue keeps existing events; network setup may evict the oldest.
 * An already pending setup event is retained and coalesced on overflow. */
static unsigned char KeyEvent_Push(volatile KeyEventQueue *queue,
                                   unsigned char event)
{
    unsigned char i;
    if (queue->count == KEY_EVENT_CAPACITY)
    {
        if (event != KEY_EVENT_NETWORK_CONFIG)
            return 0u;
        for (i = 0u; i < queue->count; ++i)
        {
            if (queue->events[i] == KEY_EVENT_NETWORK_CONFIG)
                return 1u;
        }
        (void)KeyEvent_Take(queue);
    }
    queue->events[queue->count] = event;
    ++queue->count;
    return 1u;
}

#endif
