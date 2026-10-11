#ifndef MG90S_CALIBRATION_H
#define MG90S_CALIBRATION_H

/* Open retracts the linkage; close extends it. Verify endpoints on hardware. */
#define MG90S_OPEN_PULSE_US 1000u
#define MG90S_CLOSE_PULSE_US 1600u
#define MG90S_MAX_PULSE_US \
    ((MG90S_OPEN_PULSE_US > MG90S_CLOSE_PULSE_US) ? \
        MG90S_OPEN_PULSE_US : MG90S_CLOSE_PULSE_US)

#if MG90S_OPEN_PULSE_US < 1000u || MG90S_OPEN_PULSE_US > 2000u || \
    MG90S_CLOSE_PULSE_US < 1000u || MG90S_CLOSE_PULSE_US > 2000u || \
    MG90S_OPEN_PULSE_US == MG90S_CLOSE_PULSE_US
#error MG90S pulse values must be distinct and within 1000..2000 us
#endif

#endif
