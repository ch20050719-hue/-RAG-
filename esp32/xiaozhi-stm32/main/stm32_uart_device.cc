#include "stm32_uart_device.h"

#include <driver/uart.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

namespace {
constexpr uart_port_t kUart = UART_NUM_1;
constexpr unsigned kQueueLength = 4;
constexpr char kTag[] = "STM32_UART";
QueueHandle_t command_queue = nullptr;
stm32_environment::Cache environment_cache;
portMUX_TYPE environment_mux = portMUX_INITIALIZER_UNLOCKED;

uint32_t NowMs() { return static_cast<uint32_t>(esp_timer_get_time() / 1000); }

void ReceiveTask(void*) {
    stm32_environment::Parser parser;
    uint8_t bytes[64];
    while (true) {
        const int count = uart_read_bytes(kUart, bytes, sizeof(bytes), pdMS_TO_TICKS(100));
        const uint32_t now = NowMs();
        portENTER_CRITICAL(&environment_mux);
        environment_cache.Expire(now);
        portEXIT_CRITICAL(&environment_mux);
        if (count < 0) {
            ESP_LOGE(kTag, "UART receive failed");
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        for (int i = 0; i < count; ++i) {
            stm32_environment::Sample sample;
            if (!parser.Push(bytes[i], sample))
                continue;
            portENTER_CRITICAL(&environment_mux);
            environment_cache.Update(sample, now);
            portEXIT_CRITICAL(&environment_mux);
        }
    }
}

esp_err_t SendFrame(const uint8_t* data) {
    const int written = uart_write_bytes(kUart, data, 4);
    if (written != 4) {
        return ESP_FAIL;
    }
    return uart_wait_tx_done(kUart, pdMS_TO_TICKS(100));
}

void SendTask(void*) {
    stm32_control::Packet packet;
    while (true) {
        if (xQueueReceive(command_queue, &packet, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        esp_err_t err = SendFrame(packet.bytes.data());
        if (err == ESP_OK && packet.size == 8) {
            // Allow STM32's 300 ms provisioning pause and manual-mode cleanup to finish.
            // No ACK exists; this delay cannot prove execution or mechanical position.
            vTaskDelay(pdMS_TO_TICKS(350));
            err = SendFrame(packet.bytes.data() + 4);
        }
        if (err != ESP_OK) {
            ESP_LOGE(kTag, "UART transmission failed: %s; no execution confirmation",
                     esp_err_to_name(err));
        } else {
            ESP_LOGI(kTag, "Command 0x%02X transmitted; STM32 ACK unavailable",
                     packet.bytes[packet.size - 2]);
        }
        // Bound the incoming command rate; STM32 has a 16-command FIFO.
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
}  // namespace

esp_err_t stm32_uart_device_init(gpio_num_t tx, gpio_num_t rx) {
    if (command_queue != nullptr || uart_is_driver_installed(kUart)) {
        return ESP_ERR_INVALID_STATE;
    }
    if (!GPIO_IS_VALID_OUTPUT_GPIO(tx) || !GPIO_IS_VALID_GPIO(rx) || tx == rx) {
        return ESP_ERR_INVALID_ARG;
    }
    uart_config_t config = {};
    config.baud_rate = 9600;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    esp_err_t err = uart_param_config(kUart, &config);
    if (err != ESP_OK)
        return err;
    err = uart_set_pin(kUart, tx, rx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (err != ESP_OK)
        return err;
    err = uart_driver_install(kUart, 256, 256, 0, nullptr, 0);
    if (err != ESP_OK)
        return err;
    command_queue = xQueueCreate(kQueueLength, sizeof(stm32_control::Packet));
    if (command_queue == nullptr) {
        uart_driver_delete(kUart);
        return ESP_ERR_NO_MEM;
    }
    portENTER_CRITICAL(&environment_mux);
    environment_cache = stm32_environment::Cache{};
    portEXIT_CRITICAL(&environment_mux);
    TaskHandle_t send_task = nullptr;
    if (xTaskCreate(SendTask, "stm32_uart_tx", 3072, nullptr, 4, &send_task) != pdPASS) {
        vQueueDelete(command_queue);
        command_queue = nullptr;
        uart_driver_delete(kUart);
        return ESP_ERR_NO_MEM;
    }
    if (xTaskCreate(ReceiveTask, "stm32_uart_rx", 3072, nullptr, 4, nullptr) != pdPASS) {
        vTaskDelete(send_task);
        vQueueDelete(command_queue);
        command_queue = nullptr;
        uart_driver_delete(kUart);
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(kTag, "9600 8N1, TX=%d RX=%d", static_cast<int>(tx), static_cast<int>(rx));
    return ESP_OK;
}

stm32_environment::View stm32_uart_get_environment() {
    portENTER_CRITICAL(&environment_mux);
    const auto snapshot = environment_cache;
    portEXIT_CRITICAL(&environment_mux);
    return snapshot.Get(NowMs());
}

esp_err_t stm32_uart_submit(const stm32_control::Packet& packet) {
    if (packet.size != 4 && packet.size != 8)
        return ESP_ERR_INVALID_ARG;
    if (command_queue == nullptr)
        return ESP_ERR_INVALID_STATE;
    return xQueueSend(command_queue, &packet, 0) == pdTRUE ? ESP_OK : ESP_ERR_TIMEOUT;
}
