#include "boards/bread-compact-stm32-lcd/character_animation_policy.h"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>

struct Sample {
    bool speech_state;
    bool playback_idle;
    bool expected_talking;
};

int main() {
    int checks = 0;
    auto scenario = [&](const char* name, std::initializer_list<Sample> samples) {
        bool talking = false;
        for (const auto& sample : samples) {
            talking =
                character_animation::ShouldTalk(sample.speech_state, talking, sample.playback_idle);
            ++checks;
            if (talking != sample.expected_talking) {
                std::fprintf(stderr, "Failed scenario %s at check %d\n", name, checks);
                std::exit(1);
            }
        }
    };
    // A wake tone must not start a mouth animation.
    scenario("standby and wake tone",
             {{false, true, false}, {false, false, false}, {false, true, false}});
    // Server STOP may arrive while a buffered audio tail is still playing.
    scenario("reply with tail", {{true, true, true},
                                 {true, false, true},
                                 {false, false, true},
                                 {false, false, true},
                                 {false, true, false}});
    // A temporarily empty playback queue between reply chunks is not the end.
    scenario("streaming reply gap",
             {{true, false, true}, {true, true, true}, {true, false, true}, {false, true, false}});
    // An interruption drains audio; a later reply can start a new animation.
    scenario("interruption and next reply", {{true, false, true},
                                             {false, true, false},
                                             {false, false, false},
                                             {true, false, true},
                                             {false, false, true},
                                             {false, true, false}});
    std::printf("Character animation: %d scenario checks passed\n", checks);
}
