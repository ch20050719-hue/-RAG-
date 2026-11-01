#include "usart.h"
#include <string.h>
#include "environment_protocol.h"

/* Exercise production usart.c and voice_command.c, replacing only hardware. */
void uart3_init(u32 bound);
void USART1_IRQHandler(void);
void USART2_IRQHandler(void);
void USART3_IRQHandler(void);
USART_TypeDef test_usarts[3];
GPIO_TypeDef test_gpio[2];
volatile uint32_t g_tim3_heartbeat;
static uint32_t apb1, apb2, primask, disable_count, restore_count;
static GPIO_InitTypeDef pins[2][16];
static USART_InitTypeDef uart_configs[3];
static NVIC_InitTypeDef irq_configs[4];
static int rx_enabled[3], uart_enabled[3], rx_pending[3], tx_enabled[3];
static int error_enabled[3];
static unsigned receive_reads[3];
static uint8_t transmitted[64];
static unsigned transmitted_count;
static uint8_t giz_bytes[8];
static uint32_t giz_count;
static int failures;
#define CHECK(value) do { if (!(value)) { puts("FAIL: " #value); ++failures; } } while (0)

void RCC_APB1PeriphClockCmd(uint32_t bits, int enable) { if (enable) apb1 |= bits; }
void RCC_APB2PeriphClockCmd(uint32_t bits, int enable) { if (enable) apb2 |= bits; }
void GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *config) {
    unsigned bit;
    for (bit = 0; bit < 16; ++bit) {
        if (config->GPIO_Pin & (1u << bit)) pins[port == GPIOB][bit] = *config;
    }
}
void NVIC_Init(NVIC_InitTypeDef *config) { irq_configs[config->NVIC_IRQChannel] = *config; }
void USART_Init(USART_TypeDef *uart, USART_InitTypeDef *config) { uart_configs[uart - test_usarts] = *config; }
void USART_ITConfig(USART_TypeDef *uart, int interrupt, int enable) {
    if (interrupt == USART_IT_RXNE) rx_enabled[uart - test_usarts] = enable;
    else if (interrupt == USART_IT_ERR) error_enabled[uart - test_usarts] = enable;
    else { CHECK(interrupt == USART_IT_TXE); tx_enabled[uart - test_usarts] = enable; }
}
void USART_Cmd(USART_TypeDef *uart, int enable) { uart_enabled[uart - test_usarts] = enable; }
int USART_GetITStatus(USART_TypeDef *uart, int interrupt) {
    if (interrupt == USART_IT_RXNE) return rx_pending[uart - test_usarts];
    CHECK(interrupt == USART_IT_TXE); return tx_enabled[uart - test_usarts];
}
uint8_t USART_ReceiveData(USART_TypeDef *uart) {
    ++receive_reads[uart - test_usarts];
    uart->SR &= ~(USART_FLAG_RXNE | USART_FLAG_ORE | USART_FLAG_FE | USART_FLAG_NE | USART_FLAG_PE);
    rx_pending[uart - test_usarts] = 0; return (uint8_t)uart->DR;
}
void USART_SendData(USART_TypeDef *uart, uint16_t value) {
    CHECK(uart == USART3); CHECK(transmitted_count < sizeof transmitted);
    if (transmitted_count < sizeof transmitted) transmitted[transmitted_count++] = (uint8_t)value;
}
uint32_t __get_PRIMASK(void) { return primask; }
void __disable_irq(void) { primask = 1; ++disable_count; }
void __set_PRIMASK(uint32_t value) { primask = value; ++restore_count; }
void gizPutData(uint8_t *data, uint32_t length) {
    CHECK(length == 1); if (giz_count < sizeof giz_bytes) giz_bytes[giz_count++] = *data;
}
static void byte(unsigned port, uint8_t value) {
    test_usarts[port].SR = USART_FLAG_RXNE;
    test_usarts[port].DR = value; rx_pending[port] = 1; ++g_tim3_heartbeat;
    if (port == 0) USART1_IRQHandler();
    else if (port == 1) USART2_IRQHandler();
    else USART3_IRQHandler();
}
static void frame(unsigned port, uint8_t command) {
    byte(port, 0xF4); byte(port, 0x06); byte(port, command); byte(port, 0xFB);
}
static void test_configuration(void) {
    uart1_init(9600); uart2_init(9600); uart3_init(9600);
    CHECK((apb1 & (RCC_APB1Periph_USART2 | RCC_APB1Periph_USART3)) ==
                 (RCC_APB1Periph_USART2 | RCC_APB1Periph_USART3));
    CHECK((apb2 & (RCC_APB2Periph_USART1 | RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB)) ==
                 (RCC_APB2Periph_USART1 | RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB));
    CHECK(pins[1][10].GPIO_Mode == GPIO_Mode_AF_PP);
    CHECK(pins[1][10].GPIO_Speed == GPIO_Speed_50MHz);
    CHECK(pins[1][11].GPIO_Mode == GPIO_Mode_IN_FLOATING);
    CHECK(pins[0][9].GPIO_Mode == GPIO_Mode_AF_PP && pins[0][10].GPIO_Mode == GPIO_Mode_IN_FLOATING);
    CHECK(pins[0][2].GPIO_Mode == GPIO_Mode_AF_PP && pins[0][3].GPIO_Mode == GPIO_Mode_IN_FLOATING);
    CHECK(uart_configs[2].USART_BaudRate == 9600);
    CHECK(uart_configs[2].USART_WordLength == USART_WordLength_8b);
    CHECK(uart_configs[2].USART_StopBits == USART_StopBits_1);
    CHECK(uart_configs[2].USART_Parity == USART_Parity_No);
    CHECK(uart_configs[2].USART_HardwareFlowControl == USART_HardwareFlowControl_None);
    CHECK(uart_configs[2].USART_Mode == (USART_Mode_Rx | USART_Mode_Tx));
    CHECK(!tx_enabled[0] && !tx_enabled[1] && !tx_enabled[2]);
    CHECK(rx_enabled[0] && rx_enabled[1] && rx_enabled[2]);
    CHECK(error_enabled[0] && !error_enabled[1] && error_enabled[2]);
    CHECK(uart_enabled[0] && uart_enabled[1] && uart_enabled[2]);
    CHECK(irq_configs[3].NVIC_IRQChannelCmd == ENABLE);
    CHECK(irq_configs[1].NVIC_IRQChannelPreemptionPriority == irq_configs[3].NVIC_IRQChannelPreemptionPriority);
}
static void test_independent_streams(void) {
    uint8_t command = 0;
    byte(0, 0xF4); byte(0, 0x06);
    byte(2, 0x09); byte(2, 0xFB);
    CHECK(!USART1_TakeCommand(&command)); /* Cross-UART fragments cannot form a frame. */
    byte(0, 0x01); byte(0, 0xFB);
    CHECK(USART1_TakeCommand(&command) && command == 1);
    byte(0, 0xF4); byte(2, 0xF4); byte(0, 0x06); byte(2, 0x06);
    byte(0, 0x02); byte(2, 0x0A); byte(0, 0xFB); byte(2, 0xFB);
    CHECK(USART1_TakeCommand(&command));
    CHECK(command == 2 || command == 10);
    { uint8_t first = command;
      CHECK(USART1_TakeCommand(&command)); CHECK(command != first && (command == 2 || command == 10)); }
    CHECK(!USART1_TakeCommand(&command));
}
static void test_fairness_and_modes(void) {
    uint8_t result[6] = {0}, command, i;
    for (i = 1; i <= 3; ++i) { frame(0, i); frame(2, (uint8_t)(i + 8)); }
    for (i = 0; i < 6; ++i) CHECK(USART1_TakeCommand(&result[i]));
    for (i = 1; i < 6; ++i) CHECK((result[i] < 8) != (result[i - 1] < 8));
    for (i = 2; i < 6; ++i) CHECK(result[i] == result[i - 2] + 1);
    CHECK(!USART1_TakeCommand(&command));
    for (i = 1; i <= 13; ++i) {
        frame(0, i); CHECK(USART1_TakeCommand(&command) && command == i);
        frame(2, i); CHECK(USART1_TakeCommand(&command) && command == i);
    }
    CHECK(!USART1_TakeCommand(&command));
    frame(2, 0); frame(2, 14); CHECK(!USART1_TakeCommand(&command));
    frame(2, 8); CHECK(!USART1_TakeCommand(0));
    CHECK(USART1_TakeCommand(&command) && command == 8);
    primask = 1; CHECK(!USART1_TakeCommand(&command)); CHECK(primask == 1);
    primask = 0; CHECK(!USART1_TakeCommand(&command)); CHECK(primask == 0);
    CHECK(disable_count > 0 && disable_count == restore_count);
}
static void test_cloud_unchanged(void) {
    uint8_t command;
    frame(1, 8);
    CHECK(giz_count == 4 && giz_bytes[0] == 0xF4 && giz_bytes[1] == 6 &&
          giz_bytes[2] == 8 && giz_bytes[3] == 0xFB);
    CHECK(!USART1_TakeCommand(&command));
    USART3_IRQHandler(); CHECK(!USART1_TakeCommand(&command));
}
static void test_environment_golden_frame(void) {
    EnvironmentSnapshot snapshot = {1, 1, 27, 65, 3060, 100, 200, 1275};
    const uint8_t golden[20] = {
        0xF4, 0x08, 0x02, 0x03, 0x1B, 0x41, 0xF4, 0x0B, 0xFB, 0x04,
        0x64, 0x00, 0x00, 0x00, 0xC8, 0x00, 0x00, 0x00, 0xFF, 0xFB
    };
    uint8_t encoded[20] = {0};
    CHECK(Environment_Encode(&snapshot, encoded));
    CHECK(memcmp(encoded, golden, sizeof golden) == 0);
}
static void test_environment(void) {
    EnvironmentSnapshot snapshot = {1, 1, 25, 60, 2048, 100, 200, 0x0BF4};
    uint8_t expected[20] = {0}, command;
    unsigned i;
    CHECK(Environment_Encode(&snapshot, expected));
    CHECK(expected[0] == 0xF4 && expected[1] == 8 && expected[2] == 2);
    _Static_assert(ENVIRONMENT_FRAME_SIZE == 20u, "v2 telemetry is 20 bytes");
    CHECK(expected[8] == 0xF4 && expected[9] == 0x0B);
    CHECK(expected[3] == 3 && expected[4] == 25 && expected[5] == 60);
    CHECK(expected[6] == 0 && expected[7] == 8 && expected[10] == 100);
    CHECK(expected[14] == 200 && expected[19] == 0xFB);
    { uint8_t checksum = 0; for (i = 1; i <= 17; ++i) checksum ^= expected[i];
      CHECK(expected[18] == checksum); }
    CHECK(!Environment_Encode(0, expected)); CHECK(!Environment_Encode(&snapshot, 0));
    CHECK(!USART3_PublishEnvironment(0));
    primask = 1;
    CHECK(USART3_PublishEnvironment(&snapshot)); CHECK(primask == 1);
    CHECK(tx_enabled[2] && transmitted_count == 0);
    CHECK(!USART3_PublishEnvironment(&snapshot));
    primask = 0;
    for (i = 0; i < 20; ++i) {
        if (i == 3) { frame(0, 1); frame(2, 10); }
        USART3_IRQHandler();
    }
    CHECK(!tx_enabled[2] && transmitted_count == 20);
    CHECK(memcmp(expected, transmitted, 20) == 0);
    CHECK(USART1_TakeCommand(&command) && command == 1);
    CHECK(USART1_TakeCommand(&command) && command == 10);
    CHECK(!USART1_TakeCommand(&command));
    USART3_IRQHandler(); CHECK(transmitted_count == 20);
    snapshot.adc_valid = 0;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 1);
    snapshot.adc_valid = 1; snapshot.dht_age_ms = 3001;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 2);
    snapshot.dht_valid = 0; snapshot.adc_age_ms = 3001;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 0);
    snapshot.dht_valid = 1; snapshot.dht_age_ms = 3000; snapshot.adc_age_ms = 3000;
    snapshot.temperature_c = 50; snapshot.humidity_percent = 100; snapshot.light_raw = 4096;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 3);
    snapshot.temperature_c = 51;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 2);
    snapshot.temperature_c = 25; snapshot.humidity_percent = 101;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 2);
    snapshot.humidity_percent = 60; snapshot.light_raw = 4097;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 1);
    snapshot.light_raw = 0;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 1);
    snapshot.light_raw = 1; snapshot.smoke_raw = 0;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 3);
    CHECK(expected[8] == 0 && expected[9] == 0);
    snapshot.smoke_raw = 4095;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 3);
    CHECK(expected[8] == 255 && expected[9] == 15);
    snapshot.smoke_raw = 4096;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 1);
    snapshot.smoke_raw = 65535;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 1);
    snapshot.smoke_raw = 0x0BFB;
    snapshot.dht_age_ms = 0xFFFFFFFFu;
    snapshot.adc_age_ms = 0x12345678u;
    CHECK(Environment_Encode(&snapshot, expected) && expected[3] == 0);
    CHECK(expected[10] == 255 && expected[13] == 255);
    CHECK(expected[14] == 0x78 && expected[17] == 0x12);
    CHECK(USART3_PublishEnvironment(&snapshot));
    for (i = 0; i < 20; ++i) USART3_IRQHandler();
    CHECK(transmitted_count == 40 && memcmp(expected, transmitted + 20, 20) == 0);
}
static void test_receive_errors(void) {
    uint8_t command;
    unsigned port, i, before;
    const uint32_t errors[] = {USART_FLAG_ORE, USART_FLAG_FE, USART_FLAG_NE, USART_FLAG_PE};
    for (port = 0; port <= 2; port += 2) {
        for (i = 0; i < 4; ++i) {
            frame(port, 2); /* An accepted command must survive a later bad byte. */
            byte(port, 0xF4); byte(port, 0x06); byte(port, 1);
            test_usarts[port].SR = errors[i] | USART_FLAG_RXNE;
            test_usarts[port].DR = 0xFB; rx_pending[port] = 1;
            if (port == 0) USART1_IRQHandler(); else USART3_IRQHandler();
            CHECK(USART1_TakeCommand(&command) && command == 2);
            CHECK(!USART1_TakeCommand(&command));
            frame(port, 3); CHECK(USART1_TakeCommand(&command) && command == 3);
        }
        byte(port, 0xF4); byte(port, 0x06);
        before = receive_reads[port];
        test_usarts[port].SR = USART_FLAG_ORE; rx_pending[port] = 0;
        if (port == 0) USART1_IRQHandler(); else USART3_IRQHandler();
        CHECK(receive_reads[port] == before + 1);
        CHECK(test_usarts[port].SR == 0);
        byte(port, 1); byte(port, 0xFB); CHECK(!USART1_TakeCommand(&command));
        frame(port, 4); CHECK(USART1_TakeCommand(&command) && command == 4);
    }
}
static void test_error_diagnostics_and_duplex(void) {
    USART_ControlDiagnostics a, b;
    EnvironmentSnapshot snapshot = {1, 1, 25, 60, 2048, 100, 200, 0x0BF4};
    uint8_t command, encoded[20] = {0};
    unsigned i, before = transmitted_count;
    CHECK(!USART_GetControlDiagnostics(2, &a));
    CHECK(!USART_GetControlDiagnostics(1, 0));
    primask = 1; CHECK(USART_GetControlDiagnostics(1, &a)); CHECK(primask == 1);
    primask = 0; CHECK(USART_GetControlDiagnostics(3, &b)); CHECK(primask == 0);
    CHECK(a.overrun_count == 2 && a.framing_count == 1 && a.noise_count == 1 && a.parity_count == 1);
    CHECK(b.overrun_count == 2 && b.framing_count == 1 && b.noise_count == 1 && b.parity_count == 1);
    CHECK(a.queued_commands == 0 && b.queued_commands == 0);
    CHECK(a.received_bytes > 0 && b.received_bytes > 0);
    byte(0, 0xF4); byte(0, 6); byte(0, 5);
    CHECK(USART3_PublishEnvironment(&snapshot));
    test_usarts[2].SR = USART_FLAG_ORE | USART_FLAG_FE | USART_FLAG_NE;
    USART3_IRQHandler(); /* RX recovery must not skip an already pending TXE. */
    CHECK(transmitted_count == before + 1);
    byte(0, 0xFB); CHECK(USART1_TakeCommand(&command) && command == 5);
    for (i = 1; i < 20; ++i) USART3_IRQHandler();
    CHECK(Environment_Encode(&snapshot, encoded));
    CHECK(transmitted_count == before + 20);
    CHECK(memcmp(encoded, transmitted + before, 20) == 0);
    for (i = 0; i < 65536u; ++i) {
        test_usarts[2].SR = USART_FLAG_ORE | USART_FLAG_FE | USART_FLAG_NE | USART_FLAG_PE;
        USART3_IRQHandler();
        byte(2, 0); /* Invalid data does not produce commands; byte count saturates. */
    }
    CHECK(USART_GetControlDiagnostics(3, &b));
    CHECK(b.overrun_count == UINT16_MAX && b.framing_count == UINT16_MAX);
    CHECK(b.noise_count == UINT16_MAX && b.parity_count == UINT16_MAX);
    CHECK(b.received_bytes == UINT16_MAX);
    CHECK(USART_GetControlDiagnostics(1, &a) && a.overrun_count == 2);
    frame(2, 6); CHECK(USART1_TakeCommand(&command) && command == 6);
    for (i = 0; i < 17; ++i) frame(2, 1);
    CHECK(USART_GetControlDiagnostics(3, &b));
    CHECK(b.queued_commands == 16 && b.queue_overflow_count == 1);
    g_tim3_heartbeat += 5001;
    CHECK(!USART1_TakeCommand(&command));
    CHECK(USART_GetControlDiagnostics(3, &b));
    CHECK(b.queued_commands == 0 && b.expired_count == 16);
}
int main(void) {
    test_configuration(); test_independent_streams(); test_fairness_and_modes(); test_cloud_unchanged(); test_environment();
    test_environment_golden_frame();
    test_receive_errors();
    test_error_diagnostics_and_duplex();
    if (!failures) puts("USART1/USART3 isolation, fairness, configuration and USART2 regression passed");
    return failures ? 1 : 0;
}
