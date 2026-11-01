#pragma once

#include <array>
#include <cstdint>
#include <limits>
#include <string>

namespace stm32_environment {
constexpr uint32_t kMaxAgeMs = 3000;

struct Sample {
    uint8_t flags = 0;
    uint8_t temperature = 0;
    uint8_t humidity = 0;
    uint16_t light_raw = 0;
    uint32_t dht_age_ms = 0;
    uint32_t adc_age_ms = 0;
};

// Sliding fixed-size window keeps embedded F4/FB payload bytes intact and
// recovers after noise or a truncated frame without trusting a length byte.
class Parser {
    std::array<uint8_t, 18> bytes_{};
    size_t size_ = 0;

    uint32_t ReadAge(size_t offset) const {
        uint32_t value = 0;
        for (unsigned i = 0; i < 4; ++i)
            value |= static_cast<uint32_t>(bytes_[offset + i]) << (8 * i);
        return value;
    }

public:
    bool Push(uint8_t byte, Sample& result) {
        if (size_ == bytes_.size()) {
            for (size_t i = 1; i < size_; ++i)
                bytes_[i - 1] = bytes_[i];
            --size_;
        }
        bytes_[size_++] = byte;
        if (size_ != bytes_.size() || bytes_[0] != 0xF4 || bytes_[17] != 0xFB || bytes_[1] != 8 ||
            bytes_[2] != 1 || (bytes_[3] & 0xFC) != 0)
            return false;
        if ((bytes_[3] & 1) && (bytes_[4] > 50 || bytes_[5] > 100))
            return false;
        const uint16_t light = static_cast<uint16_t>(bytes_[6] | (bytes_[7] << 8));
        if ((bytes_[3] & 2) && (light == 0 || light > 4096))
            return false;
        uint8_t checksum = 0;
        for (size_t i = 1; i <= 15; ++i)
            checksum ^= bytes_[i];
        if (checksum != bytes_[16])
            return false;
        result = Sample{bytes_[3], bytes_[4], bytes_[5], light, ReadAge(8), ReadAge(12)};
        size_ = 0;
        return true;
    }
};

struct View {
    Sample sample{};
    bool received = false;
    bool dht_valid = false;
    bool adc_valid = false;
    uint32_t dht_age_ms = 0;
    uint32_t adc_age_ms = 0;
};

class Cache {
    Sample sample_{};
    uint32_t received_ms_ = 0;
    bool received_ = false;

    static uint32_t AddAge(uint32_t source, uint32_t elapsed) {
        const auto maximum = std::numeric_limits<uint32_t>::max();
        return source > maximum - elapsed ? maximum : source + elapsed;
    }

public:
    void Update(const Sample& sample, uint32_t now_ms) {
        sample_ = sample;
        received_ms_ = now_ms;
        received_ = true;
    }

    View Get(uint32_t now_ms) const {
        const uint32_t elapsed = now_ms - received_ms_;
        const uint32_t dht_age = AddAge(sample_.dht_age_ms, elapsed);
        const uint32_t adc_age = AddAge(sample_.adc_age_ms, elapsed);
        return View{sample_,
                    received_,
                    received_ && (sample_.flags & 1) && dht_age <= kMaxAgeMs,
                    received_ && (sample_.flags & 2) && adc_age <= kMaxAgeMs,
                    dht_age,
                    adc_age};
    }

    // Called by the RX worker every bounded read, including silent periods.
    // Latch expiry so a disconnected reading cannot revive on a later clock wrap.
    void Expire(uint32_t now_ms) {
        const auto view = Get(now_ms);
        Sample updated = sample_;
        if (!view.dht_valid)
            updated.flags &= static_cast<uint8_t>(~1u);
        if (!view.adc_valid)
            updated.flags &= static_cast<uint8_t>(~2u);
        sample_ = updated;
    }
};

inline std::string ToJson(const View& view) {
    const auto value = [](bool valid, uint32_t number) {
        return valid ? std::to_string(number) : std::string("null");
    };
    return std::string("{\"received\":") + (view.received ? "true" : "false") +
           ",\"dht_valid\":" + (view.dht_valid ? "true" : "false") +
           ",\"adc_valid\":" + (view.adc_valid ? "true" : "false") +
           ",\"temperature_c\":" + value(view.dht_valid, view.sample.temperature) +
           ",\"humidity_percent_rh\":" + value(view.dht_valid, view.sample.humidity) +
           ",\"light_raw\":" + value(view.adc_valid, view.sample.light_raw) +
           ",\"dht_age_ms\":" + value(view.received, view.dht_age_ms) +
           ",\"adc_age_ms\":" + value(view.received, view.adc_age_ms) +
           ",\"max_age_ms\":3000,\"light_unit\":\"relative_raw_uncalibrated\"}";
}
}  // namespace stm32_environment
