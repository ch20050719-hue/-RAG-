// Compile the real implementation against deterministic ESP-IDF/FreeRTOS fakes.
#include "stubs/mcp_server.h"

#include <cstdlib>
#include <iostream>
#include "stm32_mcp_device.h"
#include "stm32_uart_device.cc"

namespace {
int checks = 0;
void Check(bool condition, const char* label) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL: " << label << '\n';
        std::exit(1);
    }
}
void Reset() {
    command_queue = nullptr;
    environment_cache = {};
    mock::state = mock::Runtime{};
    McpServer::GetInstance().tools.clear();
}
void Start() { Check(stm32_uart_device_init(17, 18) == ESP_OK, "init succeeds"); }
void Drain() {
    try {
        mock::state.worker(nullptr);
    } catch (const mock::StopWorker&) {
        return;
    }
    Check(false, "worker remains active until queue empty");
}
void TestInitialization() {
    Reset();
    Start();
    const auto& s = mock::state;
    Check(s.config.baud_rate == 9600 && s.config.data_bits == 8 &&
              s.config.parity == UART_PARITY_DISABLE && s.config.stop_bits == UART_STOP_BITS_1 &&
              s.config.flow_ctrl == UART_HW_FLOWCTRL_DISABLE,
          "9600 8N1 without flow control");
    Check(s.tx == 17 && s.rx == 18 && s.rts == -1 && s.cts == -1, "requested pins applied");
    Check(s.rx_buffer == 256 && s.tx_buffer == 256, "driver buffers allocated");
    Check(s.queue_length == 4 && s.item_size == sizeof(stm32_control::Packet),
          "bounded packet queue");
    Check(s.task_calls == 2 && s.worker != nullptr && s.reader != nullptr,
          "separate TX and RX tasks created");
    Check(stm32_uart_device_init(17, 18) == ESP_ERR_INVALID_STATE, "duplicate init rejected");
    Check(s.config_calls == 1, "duplicate init does not touch driver");
    for (const auto& pins : {std::array<int, 2>{-1, 18}, {34, 18}, {17, 40}, {17, 17}}) {
        Reset();
        Check(stm32_uart_device_init(pins[0], pins[1]) == ESP_ERR_INVALID_ARG,
              "invalid pins rejected");
        Check(mock::state.config_calls == 0, "invalid pins have no driver side effects");
    }
    Reset();
    mock::state.installed = true;
    Check(stm32_uart_device_init(17, 18) == ESP_ERR_INVALID_STATE, "existing driver rejected");
    Check(mock::state.config_calls == 0 && mock::state.delete_calls == 0,
          "existing driver preserved");
}
void TestInitializationFailures() {
    Reset();
    mock::state.config_result = ESP_FAIL;
    Check(stm32_uart_device_init(17, 18) == ESP_FAIL, "configuration error propagated");
    Check(mock::state.pin_calls == 0, "config failure stops pin setup");
    Reset();
    mock::state.pin_result = ESP_FAIL;
    Check(stm32_uart_device_init(17, 18) == ESP_FAIL, "pin error propagated");
    Check(mock::state.install_calls == 0, "pin failure stops install");
    Reset();
    mock::state.install_result = ESP_FAIL;
    Check(stm32_uart_device_init(17, 18) == ESP_FAIL, "driver install error propagated");
    Check(mock::state.queue_length == 0 && mock::state.delete_calls == 0,
          "failed install creates no queue");
    Reset();
    mock::state.fail_queue = true;
    Check(stm32_uart_device_init(17, 18) == ESP_ERR_NO_MEM, "queue allocation failure reported");
    Check(mock::state.delete_calls == 1 && !mock::state.installed && command_queue == nullptr,
          "queue failure releases driver");
    Reset();
    mock::state.fail_task = true;
    Check(stm32_uart_device_init(17, 18) == ESP_ERR_NO_MEM, "task allocation failure reported");
    Check(mock::state.queue_delete_calls == 1 && mock::state.delete_calls == 1 &&
              command_queue == nullptr,
          "task failure releases queue and driver");
    mock::state.fail_task = false;
    Start();
    Reset();
    mock::state.fail_task_call = 2;
    Check(stm32_uart_device_init(17, 18) == ESP_ERR_NO_MEM, "RX task allocation failure reported");
    Check(mock::state.task_delete_calls == 1 && mock::state.queue_delete_calls == 1 &&
              mock::state.delete_calls == 1 && command_queue == nullptr,
          "RX task failure deletes live TX task queue and driver");
    mock::state.fail_task_call = 0;
    Start();
}
void TestSubmission() {
    Reset();
    auto packet = *stm32_control::BuildModeCommand("auto");
    Check(stm32_uart_submit(packet) == ESP_ERR_INVALID_STATE, "uninitialized submission rejected");
    Start();
    for (size_t size : {size_t{0}, size_t{3}, size_t{5}, size_t{9}}) {
        auto invalid = packet;
        invalid.size = size;
        Check(stm32_uart_submit(invalid) == ESP_ERR_INVALID_ARG, "invalid size rejected");
    }
    Check(mock::state.queue.empty(), "invalid packets not enqueued");
    Check(stm32_uart_submit(packet) == ESP_OK, "valid packet queued");
    Check(mock::state.submit_wait == 0, "submission never waits");
    packet.bytes[2] = 0x07;
    Drain();
    Check(mock::state.frames[0][2] == 0x08, "queue owns independent copy");
    for (int i = 0; i < 4; ++i)
        Check(stm32_uart_submit(packet) == ESP_OK, "queue accepts bounded capacity");
    Check(stm32_uart_submit(packet) == ESP_ERR_TIMEOUT, "queue full reported");
    Check(mock::state.queue.size() == 4, "overflow does not append");
}
void TestSending() {
    const uint8_t frame[] = {0xF4, 0x06, 0x08, 0xFB};
    for (int written : {-1, 0, 3}) {
        Reset();
        mock::state.write_result = written;
        Check(SendFrame(frame) == ESP_FAIL, "failed or short write rejected");
        Check(mock::state.wait_calls == 0, "short write does not wait for TX");
    }
    Reset();
    mock::state.wait_result = ESP_ERR_TIMEOUT;
    Check(SendFrame(frame) == ESP_ERR_TIMEOUT, "TX timeout propagated");
    Check(mock::state.tx_wait == 100, "TX wait bounded to 100ms");
    Reset();
    Start();
    Check(stm32_uart_submit(*stm32_control::BuildDeviceCommand("door", true)) == ESP_OK,
          "device queued");
    Check(stm32_uart_submit(*stm32_control::BuildModeCommand("auto")) == ESP_OK,
          "mode queued after device");
    Drain();
    Check(mock::state.frames.size() == 3, "device two frames and mode one frame");
    Check(mock::state.frames[0][2] == 7 && mock::state.frames[1][2] == 9 &&
              mock::state.frames[2][2] == 8,
          "worker preserves manual action mode order");
    const std::vector<std::string> expected = {
        "write", "wait", "delay:350", "write", "wait", "delay:100", "write", "wait", "delay:100"};
    Check(mock::state.events == expected, "worker applies 350ms action delay and 100ms rate limit");
    Reset();
    Start();
    mock::state.write_result = -1;
    Check(stm32_uart_submit(*stm32_control::BuildDeviceCommand("light", true)) == ESP_OK,
          "failed transmission queued");
    Drain();
    Check(mock::state.frames.size() == 1, "manual transmission failure prevents action send");
    Check(mock::state.events == std::vector<std::string>{"write", "delay:100"},
          "failed send still rate limited");
}
std::vector<uint8_t> EnvironmentFrame(uint8_t flags = 3) {
    std::vector<uint8_t> frame{0xF4, 8, 1, flags, 30, 70, 0xF4, 0x0B, 100,
                               0,    0, 0, 200,   0,  0,  0,    0,    0xFB};
    for (size_t i = 1; i <= 15; ++i)
        frame[16] ^= frame[i];
    return frame;
}
void Receive() {
    try {
        mock::state.reader(nullptr);
    } catch (const mock::StopWorker&) {
        return;
    }
    Check(false, "RX worker continues until fake input drained");
}
void TestReceivingAndTool() {
    Reset();
    Start();
    auto view = stm32_uart_get_environment();
    Check(!view.received && mock::state.read_calls == 0,
          "snapshot before telemetry never blocks UART");
    auto frame = EnvironmentFrame();
    mock::state.incoming.push_back({0, 0xFB, 0xF4, 8, 1});
    mock::state.incoming.emplace_back(frame.begin(), frame.begin() + 5);
    mock::state.incoming.emplace_back(frame.begin() + 5, frame.end());
    mock::state.now_ms = 1000;
    Receive();
    view = stm32_uart_get_environment();
    Check(view.dht_valid && view.adc_valid && view.sample.temperature == 30 &&
              view.sample.humidity == 70,
          "real RX worker parses noise truncated frames and fragmented valid frame");
    Check(mock::state.read_wait == 100 && mock::state.critical_depth == 0,
          "RX wait bounded and critical sections balanced");
    STM32Mcp::Register();
    const auto& tools = McpServer::GetInstance().tools;
    Check(tools.size() == 3 && tools.count("self.stm32.set_device") == 1 &&
              tools.count("self.stm32.set_mode") == 1,
          "environment registration retains both control tools");
    const auto& tool = tools.at("self.stm32.get_environment");
    Check(tool.properties.size() == 0, "environment tool has no invented input");
    const int read_calls = mock::state.read_calls;
    const auto json = std::get<std::string>(tool.callback(PropertyList()));
    Check(json.find("\"temperature_c\":30") != std::string::npos &&
              json.find("\"light_raw\":3060") != std::string::npos,
          "registered MCP callback returns actual readings");
    Check(mock::state.read_calls == read_calls && mock::state.queue.empty(),
          "MCP callback reads cache without serial IO or command submission");
    mock::state.now_ms = 3901;
    const auto stale = std::get<std::string>(tool.callback(PropertyList()));
    Check(stale.find("\"temperature_c\":null") != std::string::npos &&
              stale.find("\"light_raw\":null") != std::string::npos,
          "disconnected telemetry becomes null in real callback");
    frame = EnvironmentFrame(2);
    frame[4] = 255;
    frame[5] = 255;
    frame[16] = 0;
    for (size_t i = 1; i <= 15; ++i)
        frame[16] ^= frame[i];
    mock::state.incoming.push_back(frame);
    Receive();
    view = stm32_uart_get_environment();
    Check(!view.dht_valid && view.adc_valid, "RX keeps valid ADC when DHT failed");
    frame = EnvironmentFrame();
    frame[16] ^= 1;
    mock::state.incoming.push_back(frame);
    Receive();
    Check(!stm32_uart_get_environment().dht_valid, "corrupt frame never overwrites cache");
}
}  // namespace
int main() {
    TestInitialization();
    TestInitializationFailures();
    TestSubmission();
    TestSending();
    TestReceivingAndTool();
    std::cout << "PASS: " << checks
              << " real UART implementation checks with mocked ESP-IDF/FreeRTOS\n";
}
