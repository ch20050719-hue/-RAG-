#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <deque>
#include <stdexcept>
#include <string>
#include <vector>

using esp_err_t = int;
constexpr int ESP_OK = 0, ESP_FAIL = -1, ESP_ERR_INVALID_STATE = 1;
constexpr int ESP_ERR_INVALID_ARG = 2, ESP_ERR_NO_MEM = 3, ESP_ERR_TIMEOUT = 4;
inline const char* esp_err_to_name(int) { return "mock error"; }
using gpio_num_t = int;
#define GPIO_IS_VALID_GPIO(pin) ((pin) >= 0 && (pin) < 40)
#define GPIO_IS_VALID_OUTPUT_GPIO(pin) ((pin) >= 0 && (pin) < 34)
using uart_port_t = int;
constexpr int UART_NUM_1 = 1, UART_DATA_8_BITS = 8, UART_PARITY_DISABLE = 0;
constexpr int UART_STOP_BITS_1 = 1, UART_HW_FLOWCTRL_DISABLE = 0;
constexpr int UART_SCLK_DEFAULT = 0, UART_PIN_NO_CHANGE = -1;
struct uart_config_t {
    int baud_rate, data_bits, parity, stop_bits, flow_ctrl, source_clk;
};
using TickType_t = unsigned;
using QueueHandle_t = void*;
using TaskHandle_t = void*;
using portMUX_TYPE = int;
#define portMUX_INITIALIZER_UNLOCKED 0
constexpr int pdTRUE = 1, pdPASS = 1;
constexpr unsigned portMAX_DELAY = 0xFFFFFFFFu;
#define pdMS_TO_TICKS(ms) (static_cast<unsigned>(ms))
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGI(...) ((void)0)

namespace mock {
struct StopWorker {};
struct Runtime {
    bool installed = false, fail_queue = false, fail_task = false;
    int config_result = ESP_OK, pin_result = ESP_OK, install_result = ESP_OK;
    int write_result = 4, wait_result = ESP_OK;
    int config_calls = 0, pin_calls = 0, install_calls = 0, delete_calls = 0;
    int queue_delete_calls = 0, task_calls = 0, wait_calls = 0;
    int fail_task_call = 0, task_delete_calls = 0, read_calls = 0, critical_depth = 0;
    uint32_t now_ms = 0;
    unsigned read_wait = 0;
    int tx = -1, rx = -1, rts = 0, cts = 0, rx_buffer = 0, tx_buffer = 0;
    unsigned queue_length = 0, item_size = 0, submit_wait = 123, tx_wait = 0;
    uart_config_t config{};
    std::deque<std::vector<uint8_t>> queue;
    std::vector<std::array<uint8_t, 4>> frames;
    std::vector<std::string> events;
    void (*worker)(void*) = nullptr;
    void (*reader)(void*) = nullptr;
    std::deque<std::vector<uint8_t>> incoming;
};
inline Runtime state;
}  // namespace mock
inline bool uart_is_driver_installed(int) { return mock::state.installed; }
inline int uart_param_config(int, const uart_config_t* config) {
    ++mock::state.config_calls;
    mock::state.config = *config;
    return mock::state.config_result;
}
inline int uart_set_pin(int, int tx, int rx, int rts, int cts) {
    auto& s = mock::state;
    ++s.pin_calls;
    s.tx = tx;
    s.rx = rx;
    s.rts = rts;
    s.cts = cts;
    return s.pin_result;
}
inline int uart_driver_install(int, int rx, int tx, int, void*, int) {
    auto& s = mock::state;
    ++s.install_calls;
    s.rx_buffer = rx;
    s.tx_buffer = tx;
    if (s.install_result == ESP_OK)
        s.installed = true;
    return s.install_result;
}
inline int uart_driver_delete(int) {
    ++mock::state.delete_calls;
    mock::state.installed = false;
    return ESP_OK;
}
inline QueueHandle_t xQueueCreate(unsigned length, unsigned size) {
    auto& s = mock::state;
    s.queue_length = length;
    s.item_size = size;
    return s.fail_queue ? nullptr : &s;
}
inline void vQueueDelete(QueueHandle_t) { ++mock::state.queue_delete_calls; }
inline int xTaskCreate(void (*worker)(void*), const char* name, unsigned, void*, unsigned,
                       TaskHandle_t* handle) {
    auto& s = mock::state;
    ++s.task_calls;
    if (s.fail_task || s.fail_task_call == s.task_calls)
        return 0;
    if (std::string(name) == "stm32_uart_rx")
        s.reader = worker;
    else
        s.worker = worker;
    if (handle)
        *handle = reinterpret_cast<void*>(static_cast<uintptr_t>(s.task_calls));
    return pdPASS;
}
inline void vTaskDelete(TaskHandle_t) { ++mock::state.task_delete_calls; }
inline int64_t esp_timer_get_time() { return static_cast<int64_t>(mock::state.now_ms) * 1000; }
inline void portENTER_CRITICAL(portMUX_TYPE*) { ++mock::state.critical_depth; }
inline void portEXIT_CRITICAL(portMUX_TYPE*) { --mock::state.critical_depth; }
inline int uart_read_bytes(int, void* destination, unsigned size, unsigned wait) {
    auto& s = mock::state;
    ++s.read_calls;
    s.read_wait = wait;
    if (s.incoming.empty())
        throw mock::StopWorker{};
    auto bytes = s.incoming.front();
    s.incoming.pop_front();
    if (bytes.size() > size)
        throw std::runtime_error("mock chunk too large");
    std::memcpy(destination, bytes.data(), bytes.size());
    return static_cast<int>(bytes.size());
}
inline int xQueueSend(QueueHandle_t, const void* data, unsigned wait) {
    auto& s = mock::state;
    s.submit_wait = wait;
    if (s.queue.size() >= s.queue_length)
        return 0;
    const auto* bytes = static_cast<const uint8_t*>(data);
    s.queue.emplace_back(bytes, bytes + s.item_size);
    return pdTRUE;
}
inline int xQueueReceive(QueueHandle_t, void* data, unsigned) {
    auto& s = mock::state;
    if (s.queue.empty())
        throw mock::StopWorker{};
    std::memcpy(data, s.queue.front().data(), s.item_size);
    s.queue.pop_front();
    return pdTRUE;
}
inline int uart_write_bytes(int, const void* data, size_t size) {
    auto& s = mock::state;
    if (size != 4)
        return -1;
    std::array<uint8_t, 4> frame{};
    std::memcpy(frame.data(), data, 4);
    s.frames.push_back(frame);
    s.events.push_back("write");
    return s.write_result;
}
inline int uart_wait_tx_done(int, unsigned wait) {
    auto& s = mock::state;
    ++s.wait_calls;
    s.tx_wait = wait;
    s.events.push_back("wait");
    return s.wait_result;
}
inline void vTaskDelay(unsigned delay) {
    mock::state.events.push_back("delay:" + std::to_string(delay));
}
