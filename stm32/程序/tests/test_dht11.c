#include <assert.h>
#include <stddef.h>
#include <stdint.h>

#include "../HARDWARE/DHT11/dht11.h"

static int levels[1000];
static size_t count;
static size_t cursor;
static int default_level;

static void add(int level) { levels[count++] = level; }

static void add_byte(uint8_t value)
{
    int bit;
    for (bit = 7; bit >= 0; --bit) {
        add(0); add(1);                  /* bit begins low, then rises */
        add((value >> bit) & 1);         /* sample after 40 us */
        if ((value >> bit) & 1) add(1);  /* wait for high pulse to finish */
        add(0);
    }
}

static void frame(uint8_t checksum)
{
    count = cursor = 0;
    default_level = 0;
    add(0); add(1); /* response low */
    add(1); add(0); /* response high */
    add_byte(50); add_byte(0); add_byte(23); add_byte(0);
    add_byte(checksum);
}

void RCC_APB2PeriphClockCmd(uint32_t p, uint32_t e) { (void)p; (void)e; }
void GPIO_PinRemapConfig(uint32_t r, uint32_t e) { (void)r; (void)e; }
void GPIO_Init(void *p, GPIO_InitTypeDef *c) { (void)p; (void)c; }
void GPIO_ResetBits(void *p, uint32_t pin) { (void)p; (void)pin; }
void GPIO_SetBits(void *p, uint32_t pin) { (void)p; (void)pin; }
int GPIO_ReadInputDataBit(void *p, uint32_t pin)
{
    (void)p; (void)pin;
    return cursor < count ? levels[cursor++] : default_level;
}
void Delay_ms(unsigned int ms) { (void)ms; }
void Delay_us(unsigned int us) { (void)us; }

int main(void)
{
    u8 humi = 9, temp = 8;
    frame(73);
    assert(DHT11_Read_Data(&humi, &temp) == DHT11_READ_OK);
    assert(humi == 50 && temp == 23);

    humi = 9; temp = 8;
    frame(72);
    assert(DHT11_Read_Data(&humi, &temp) == DHT11_READ_CHECKSUM);
    assert(humi == 9 && temp == 8);

    count = cursor = 0;
    default_level = 1; /* sensor never pulls the data line low */
    assert(DHT11_Read_Data(&humi, &temp) == DHT11_READ_TIMEOUT);
    assert(humi == 9 && temp == 8);

    humi = 9; temp = 8;
    count = cursor = 0; /* sensor holds the data line low */
    default_level = 0;
    assert(DHT11_Read_Data(&humi, &temp) == DHT11_READ_TIMEOUT);
    assert(humi == 9 && temp == 8);

    frame(73); /* reconnect after timeout */
    assert(DHT11_Read_Data(&humi, &temp) == DHT11_READ_OK);
    assert(humi == 50 && temp == 23);

    humi = 9; temp = 8;
    frame(73);
    count = 4; /* response completed, first bit never rises */
    assert(DHT11_Read_Data(&humi, &temp) == DHT11_READ_TIMEOUT);
    assert(humi == 9 && temp == 8);
    return 0;
}
