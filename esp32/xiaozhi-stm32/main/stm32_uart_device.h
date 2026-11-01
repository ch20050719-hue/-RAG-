#pragma once

#include <driver/gpio.h>
#include <esp_err.h>
#include "stm32_control_protocol.h"
#include "stm32_environment.h"

// Startup-only initialization. The UART is dedicated to the STM32 control link.
esp_err_t stm32_uart_device_init(gpio_num_t tx, gpio_num_t rx);

// Nonblocking submission; ESP_OK means queued, not acknowledged by STM32.
esp_err_t stm32_uart_submit(const stm32_control::Packet& packet);

// Reads a synchronized cache snapshot without waiting for serial traffic.
stm32_environment::View stm32_uart_get_environment();
