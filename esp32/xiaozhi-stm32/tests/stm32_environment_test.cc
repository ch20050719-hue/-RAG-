#include "stm32_environment.h"
#include <cstdlib>
#include <iostream>
#ifdef WITH_STM32_ENV_ENCODER
#include "environment_protocol.h"
#endif

namespace {
int checks = 0;
void Check(bool value, const char* label) {
    ++checks;
    if (!value) {
        std::cerr << "FAIL: " << label << '\n';
        std::exit(1);
    }
}
using Frame = std::array<uint8_t, 18>;
void Seal(Frame& frame) {
    frame[16] = 0;
    for (size_t i = 1; i <= 15; ++i)
        frame[16] ^= frame[i];
}
Frame Make(uint8_t flags = 3, uint32_t dht_age = 100, uint32_t adc_age = 200) {
    Frame frame{0xF4, 8, 1, flags, 27, 65, 0xF4, 0x0B};
    for (unsigned i = 0; i < 4; ++i) {
        frame[8 + i] = static_cast<uint8_t>(dht_age >> (i * 8));
        frame[12 + i] = static_cast<uint8_t>(adc_age >> (i * 8));
    }
    frame[17] = 0xFB;
    Seal(frame);
    return frame;
}
bool Feed(stm32_environment::Parser& parser, const Frame& frame,
          stm32_environment::Sample& sample) {
    bool accepted = false;
    for (auto byte : frame)
        accepted |= parser.Push(byte, sample);
    return accepted;
}
void TestParser() {
    stm32_environment::Parser parser;
    stm32_environment::Sample sample;
    auto frame = Make();
    Check(Feed(parser, frame, sample), "valid frame accepted");
    Check(sample.temperature == 27 && sample.humidity == 65 && sample.light_raw == 3060,
          "sensor fields decoded little endian, embedded start retained");
    Check(sample.dht_age_ms == 100 && sample.adc_age_ms == 200, "independent sample ages decoded");
    frame = Make(3, 0xFBF4, 0xF4FB);
    Check(Feed(parser, frame, sample), "embedded head/tail in payload accepted");
    for (size_t index : {size_t{1}, size_t{2}, size_t{3}, size_t{4}, size_t{5}, size_t{7},
                         size_t{16}, size_t{17}}) {
        frame = Make();
        const uint8_t values[] = {0, 0, 0, 4, 51, 101, 17};
        if (index == 1 || index == 2)
            frame[index] = values[index];
        else if (index == 3)
            frame[index] = 4;
        else if (index == 4)
            frame[index] = 51;
        else if (index == 5)
            frame[index] = 101;
        else if (index == 7)
            frame[index] = 17;
        else
            frame[index] ^= 1;
        if (index < 16)
            Seal(frame);
        parser = {};
        Check(!Feed(parser, frame, sample), "invalid schema range checksum or tail rejected");
        Check(Feed(parser, Make(), sample), "valid frame resynchronizes after corruption");
    }
    parser = {};
    for (auto byte : {uint8_t{0}, uint8_t{0xFB}, uint8_t{0xF4}, uint8_t{8}, uint8_t{1}})
        parser.Push(byte, sample);
    Check(Feed(parser, Make(), sample), "noise and truncated prefix resynchronize");
    frame = Make();
    frame[4] = 50;
    frame[5] = 100;
    frame[6] = 0;
    frame[7] = 16;
    Seal(frame);
    Check(Feed(parser, frame, sample), "upper physical ranges accepted");
    frame = Make(2);
    frame[4] = 255;
    frame[5] = 255;
    Seal(frame);
    Check(Feed(parser, frame, sample), "invalid DHT bytes do not discard valid ADC");
    frame = Make(1);
    frame[6] = 255;
    frame[7] = 255;
    Seal(frame);
    Check(Feed(parser, frame, sample), "invalid ADC bytes do not discard valid DHT");
    frame = Make();
    frame[6] = 0;
    frame[7] = 0;
    Seal(frame);
    Check(!Feed(parser, frame, sample), "valid flag cannot claim zero ADC");
}
void TestFreshnessAndJson() {
    stm32_environment::Cache cache;
    auto view = cache.Get(0);
    Check(!view.dht_valid && !view.adc_valid && !view.received,
          "startup has no fabricated samples");
    auto json = stm32_environment::ToJson(view);
    Check(json.find("\"temperature_c\":null") != std::string::npos &&
              json.find("\"light_raw\":null") != std::string::npos,
          "missing readings serialize null");
    stm32_environment::Parser parser;
    stm32_environment::Sample sample;
    Feed(parser, Make(3, 100, 200), sample);
    cache.Update(sample, 0xFFFFFFF0u);
    view = cache.Get(0x20u);
    Check(view.dht_valid && view.adc_valid && view.dht_age_ms == 148 && view.adc_age_ms == 248,
          "elapsed receive time accumulates across uint32 wrap");
    view = cache.Get(0xFFFFFFF0u + 2800u);
    Check(view.dht_valid && view.adc_valid, "age 3000ms remains valid");
    view = cache.Get(0xFFFFFFF0u + 2801u);
    Check(view.dht_valid && !view.adc_valid, "ADC expires independently");
    view = cache.Get(0xFFFFFFF0u + 2901u);
    Check(!view.dht_valid && !view.adc_valid, "disconnected cache expires");
    cache.Expire(0xFFFFFFF0u + 2901u);
    view = cache.Get(0xFFFFFFF0u);
    Check(!view.dht_valid && !view.adc_valid,
          "latched expiry prevents revival after another timer wrap");
    Feed(parser, Make(2, 0xFFFFFFFFu, 0), sample);
    cache.Update(sample, 100);
    view = cache.Get(101);
    Check(!view.dht_valid && view.adc_valid, "invalid DHT does not invalidate ADC");
    Check(view.dht_age_ms == 0xFFFFFFFFu, "age addition saturates instead of overflowing");
    json = stm32_environment::ToJson(view);
    Check(json.find("\"humidity_percent_rh\":null") != std::string::npos &&
              json.find("\"light_raw\":3060") != std::string::npos,
          "formatter exposes only valid readings");
    Check(json.find("relative_raw_uncalibrated") != std::string::npos,
          "light units explicitly uncalibrated");
    Feed(parser, Make(0), sample);
    cache.Update(sample, 200);
    Check(!cache.Get(200).dht_valid && !cache.Get(200).adc_valid,
          "new invalid frame replaces previous valid state");
    Feed(parser, Make(3, 3001, 3001), sample);
    cache.Update(sample, 200);
    Check(!cache.Get(200).dht_valid && !cache.Get(200).adc_valid,
          "source stale values rejected at receive");
}
#ifdef WITH_STM32_ENV_ENCODER
void TestActualStm32Encoder() {
    struct Case {
        EnvironmentSnapshot source;
        bool dht_valid;
        bool adc_valid;
    };
    const Case cases[] = {{{1, 1, 27, 65, 3060, 100, 200}, true, true},
                          {{1, 1, 51, 65, 3060, 100, 200}, false, true},
                          {{1, 1, 27, 101, 3060, 100, 200}, false, true},
                          {{1, 1, 27, 65, 4097, 100, 200}, true, false},
                          {{1, 1, 27, 65, 0, 100, 200}, true, false},
                          {{0, 0, 255, 255, 65535, 0xFFFFFFFFu, 0xFFFFFFFFu}, false, false},
                          {{1, 1, 27, 65, 3060, 3001, 200}, false, true},
                          {{1, 1, 27, 65, 3060, 100, 3001}, true, false},
                          {{1, 1, 27, 65, 3060, 0xFFFFFFFFu, 0xF4FBF4FBu}, false, false},
                          {{1, 1, 50, 100, 4096, 3000, 3000}, true, true},
                          {{1, 1, 0, 0, 1, 0, 0}, true, true}};
    for (const auto& item : cases) {
        Frame frame{};
        Check(Environment_Encode(&item.source, frame.data()) == 1,
              "actual STM32 encoder emits frame");
        stm32_environment::Parser parser;
        stm32_environment::Sample sample;
        Check(Feed(parser, frame, sample), "ESP parser accepts actual STM32 frame");
        stm32_environment::Cache cache;
        cache.Update(sample, 0xFFFFFFF0u);
        const auto view = cache.Get(0xFFFFFFF0u);
        Check(view.dht_valid == item.dht_valid && view.adc_valid == item.adc_valid,
              "wire roundtrip preserves independent sensor validity");
        Check(view.sample.temperature == item.source.temperature_c &&
                  view.sample.humidity == item.source.humidity_percent &&
                  view.sample.light_raw == item.source.light_raw &&
                  view.dht_age_ms == item.source.dht_age_ms &&
                  view.adc_age_ms == item.source.adc_age_ms,
              "actual wire bytes and uint32 ages decode without truncation");
        const auto json = stm32_environment::ToJson(view);
        Check((json.find("\"temperature_c\":null") != std::string::npos) == !item.dht_valid &&
                  (json.find("\"humidity_percent_rh\":null") != std::string::npos) ==
                      !item.dht_valid &&
                  (json.find("\"light_raw\":null") != std::string::npos) == !item.adc_valid,
              "actual encoded unavailable readings remain null in tool formatter");
        const auto elapsed = cache.Get(0x20u);
        Check(elapsed.dht_valid == (item.dht_valid && item.source.dht_age_ms <= 2952) &&
                  elapsed.adc_valid == (item.adc_valid && item.source.adc_age_ms <= 2952),
              "actual source ages accumulate 48ms across ESP timer wrap");
    }
}
#endif
}  // namespace
int main() {
    TestParser();
    TestFreshnessAndJson();
#ifdef WITH_STM32_ENV_ENCODER
    TestActualStm32Encoder();
#endif
    std::cout << "PASS: " << checks << " environment parser/cache/formatter checks\n";
}
