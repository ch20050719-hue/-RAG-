#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "menu.h"
#include "MG90S.h"
#include "motor.h"

/* Decode the real OLED driver's bit-banged I2C into SSD1306 display RAM. */
static unsigned char ram[8][128];
static unsigned char page, column, scl = 1u, sda = 1u;
static unsigned char active, bits, byte_value, packet[3], packet_size;
static unsigned writes;
static uint8_t door_target, scene, motion;
u8 modeee, LEDFlag, FanFlag, CurtainFlag, Curtain_OFF_Flag, Curtain_ON_Flag;

static void ReceivePacket(void)
{
    unsigned char command;
    if (packet_size != 3u || packet[0] != 0x78u) return;
    if (packet[1] == 0x40u) {
        if (page >= 8u || column >= 128u) {
            fprintf(stderr, "OLED write outside 128x64 display\n");
            exit(2);
        }
        ram[page][column] = packet[2];
        column = (unsigned char)((column + 1u) % 128u);
        ++writes;
    } else {
        command = packet[2];
        if ((command & 0xf8u) == 0xb0u) page = command & 7u;
        else if ((command & 0xf0u) == 0x10u)
            column = (unsigned char)((column & 15u) | ((command & 15u) << 4));
        else if ((command & 0xf0u) == 0u)
            column = (unsigned char)((column & 0xf0u) | (command & 15u));
    }
}

void GPIO_WriteBit(void *port, uint16_t pin, BitAction value)
{
    unsigned char high = value != Bit_RESET;
    (void)port;
    if (pin == GPIO_Pin_0) {
        if (scl && sda && !high) {
            active = 1u; bits = 0u; byte_value = 0u; packet_size = 0u;
        } else if (scl && !sda && high && active) {
            ReceivePacket(); active = 0u;
        }
        sda = high;
    } else if (pin == GPIO_Pin_1) {
        if (!scl && high && active) {
            if (bits < 8u) {
                byte_value = (unsigned char)((byte_value << 1) | sda);
                ++bits;
            } else {
                if (packet_size < 3u) packet[packet_size++] = byte_value;
                bits = 0u; byte_value = 0u;
            }
        }
        scl = high;
    }
}

void GPIO_Init(void *port, GPIO_InitTypeDef *init) { (void)port; (void)init; }
void RCC_APB2PeriphClockCmd(uint32_t clock, int enable) { (void)clock; (void)enable; }
u8 DHT11_Read_Data(u8 *humi, u8 *temp) { *humi = 50u; *temp = 25u; return 0u; }
u8 ADCX_ReadValue(u8 channel, u16 *value) { (void)channel; *value = 100u; return 1u; }
uint8_t MG90S_GetCommandedTarget(void) { return door_target; }
void MG90S_Open(void) { door_target = MG90S_COMMAND_OPEN; }
void MG90S_Close(void) { door_target = MG90S_COMMAND_CLOSE; }
void HomeScene_Apply(uint8_t value) { scene = value; }
uint8_t HomeScene_GetCurrent(void) { return scene; }
u8 MOTOR_GetMotionStatus(void) { return motion; }
void USB_ON(u8 num) { (void)num; }
void USB_OFF(u8 num) { (void)num; }

static unsigned failures, cases;
static void EqualFrame(const unsigned char expected[8][128], const char *name)
{
    ++cases;
    if (memcmp(ram, expected, sizeof(ram)) != 0) {
        fprintf(stderr, "FAIL: %s leaves old screen pixels\n", name);
        ++failures;
    }
}

static void Render(uint8_t control_page, uint8_t selection)
{
    if (control_page == 1u) OLED_controlDevicePage1();
    else if (control_page == 2u) OLED_controlDevicePage2();
    else OLED_controlDoorPage();
    OLED_Option_open(selection);
}

/* Build the expected Chinese layout independently of the menu renderer. */
static void ExpectedChineseDoor(uint8_t target, uint8_t selection,
                                unsigned char expected[8][128])
{
    OLED_Clear();
    OLED_ShowChinese(1u, 3u, 28u); /* da */
    OLED_ShowChinese(1u, 4u, 29u); /* kai */
    OLED_ShowChinese(1u, 5u, 45u); /* men */
    OLED_ShowChinese(1u, 6u, 46u); /* suo */
    OLED_ShowChinese(2u, 3u, 30u); /* guan */
    OLED_ShowChinese(2u, 4u, 31u); /* bi */
    OLED_ShowChinese(2u, 5u, 45u);
    OLED_ShowChinese(2u, 6u, 46u);
    OLED_ShowChinese(3u, 3u, 47u); /* mu */
    OLED_ShowChinese(3u, 4u, 48u); /* biao */
    if (target == MG90S_COMMAND_OPEN || target == MG90S_COMMAND_CLOSE) {
        OLED_ShowChinese(3u, 5u, target == MG90S_COMMAND_OPEN ? 18u : 19u);
        OLED_ShowChinese(3u, 6u, 45u);
    } else {
        OLED_ShowChinese(3u, 5u, 49u); /* wei */
        OLED_ShowChinese(3u, 6u, 50u); /* ding */
    }
    OLED_Option_open(selection);
    memcpy(expected, ram, sizeof(ram));
}

static void CheckChineseDoor(uint8_t target, uint8_t selection)
{
    unsigned char expected[8][128];
    unsigned char previous[8][128];
    memcpy(previous, ram, sizeof(ram));
    ExpectedChineseDoor(target, selection, expected);
    memcpy(ram, previous, sizeof(ram));
    door_target = target;
    Render(3u, selection);
    EqualFrame(expected, "Chinese door labels and target align at x=32, row four blank");
}

static void SaveImage(const char *name)
{
    FILE *image = NULL;
    unsigned x, y;
    if (fopen_s(&image, name, "wb") != 0 || image == NULL) exit(3);
    fprintf(image, "P1\n128 64\n");
    for (y = 0; y < 64u; ++y) {
        for (x = 0; x < 128u; ++x)
            fprintf(image, "%u ", (ram[y / 8u][x] >> (y % 8u)) & 1u);
        fputc('\n', image);
    }
    fclose(image);
}

int main(void)
{
    unsigned char expected[8][128];
    uint8_t from, to, target, selection, flags;
    char name[80];
    unsigned before;
    door_target = MG90S_COMMAND_OPEN;
    for (from = 1u; from <= 3u; ++from) {
        for (to = 1u; to <= 3u; ++to) {
            if (from == to) continue;
            OLED_Clear(); Render(to, 1u); memcpy(expected, ram, sizeof(ram));
            OLED_Clear(); Render(from, 1u); Render(to, 1u);
            sprintf_s(name, sizeof(name), "control page %u -> %u", from, to);
            EqualFrame(expected, name);
        }
    }
    for (to = 1u; to <= 3u; ++to) {
        uint8_t count = to == 3u ? 2u : 4u;
        for (selection = 1u; selection <= count; ++selection) {
            OLED_Clear(); Render(to, selection); memcpy(expected, ram, sizeof(ram));
            Render(to, count); Render(to, selection);
            EqualFrame(expected, "selection arrow moves without damaging menu text");
        }
    }
    OLED_Clear(); Render(3u, 1u);
    for (target = MG90S_COMMAND_CLOSE; target <= MG90S_COMMAND_CLOSE + 2u; ++target) {
        door_target = (uint8_t)(target % 3u);
        Render(3u, 2u); memcpy(expected, ram, sizeof(ram));
        OLED_Clear(); Render(3u, 2u);
        EqualFrame(expected, "door target text changes without trailing pixels");
    }
    before = writes; Render(3u, 1u);
    ++cases;
    if (writes - before >= 1024u) {
        fprintf(stderr, "FAIL: unchanged control page clears the whole display\n");
        ++failures;
    }
    OLED_Clear(); Menu11(); memcpy(expected, ram, sizeof(ram));
    scene = 1u; motion = WINDOW_MOTION_OPENING; Menu11();
    scene = 2u; motion = WINDOW_MOTION_CLOSING; Menu11();
    scene = 0u; motion = WINDOW_MOTION_IDLE; Menu11();
    EqualFrame(expected, "scene and motion labels erase prior longer text");
    for (flags = 0u; flags < 8u; ++flags) {
        LEDFlag = flags & 1u; FanFlag = (flags >> 1) & 1u; CurtainFlag = (flags >> 2) & 1u;
        Menu11(); memcpy(expected, ram, sizeof(ram));
        OLED_Clear(); Menu11();
        EqualFrame(expected, "Chinese status fields update in their reserved cells");
    }
    OLED_Clear(); Render(3u, 1u);
    for (target = MG90S_COMMAND_UNKNOWN; target <= MG90S_COMMAND_CLOSE; ++target) {
        CheckChineseDoor(target, 1u);
        CheckChineseDoor(target, 2u);
    }
    CheckChineseDoor(MG90S_COMMAND_UNKNOWN, 1u);
    door_target = MG90S_COMMAND_OPEN;
    OLED_Clear(); Render(3u, 1u); Render(1u, 1u); SaveImage("control-light-fan.pbm");
    Render(2u, 1u); SaveImage("control-window-mode.pbm");
    Render(3u, 1u); SaveImage("control-door.pbm");
    OLED_Clear(); Menu11(); SaveImage("status.pbm");
    printf("OLED menu: %u cases, %u failures\n", cases, failures);
    return failures ? 1 : 0;
}
