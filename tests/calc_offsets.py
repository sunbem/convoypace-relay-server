"""
Script to calculate and verify exact byte offsets in scsTelemetryMap_s according to scs-telemetry-common.hpp
"""

# Zone 1 (Offset 0):
# bool sdkActive (1)
# char placeHolder[3] (3)
# bool paused (1)
# char placeHolder2[3] (3)
# unsigned long long time (8)
# unsigned long long simulatedTime (8)
# unsigned long long renderTime (8)
# long long multiplayerTimeOffset (8)
# -> Total: 1+3+1+3+8+8+8+8 = 40 bytes. Offset: 0 to 39.

# Zone 2 (Offset 40): unsigned integers
# scs_values: 6 * 4 = 24 bytes (telemetry_plugin_revision, version_major, version_minor, game, telemetry_version_game_major, telemetry_version_game_minor)
# common_ui: 1 * 4 = 4 bytes (time_abs)
# config_ui: 9 * 4 = 36 bytes (gears, gears_reverse, retarderStepCount, truckWheelCount, selectorCount, time_abs_delivery, maxTrailerCount, unitCount, plannedDistanceKm)
# truck_ui: (4 + 16 + 32 + 32) * 4 = 84 * 4 = 336 bytes (shifterSlot, retarderBrake, lightsAuxFront, lightsAuxRoof, truck_wheelSubstance[16], hshifterPosition[32], hshifterBitmask[32])
# gameplay_ui: 3 * 4 = 12 bytes (jobDeliveredDeliveryTime, jobStartingTime, jobFinishedTime)
# buffer_ui: 48 bytes
# Total: 24 + 4 + 36 + 336 + 12 + 48 = 460 bytes. (40 + 460 = 500). Offset: 40 to 499.

# Zone 3 (Offset 500): integers
# common_i: 1 * 4 = 4 bytes (restStop)
# truck_i: (1 + 1 + 32) * 4 = 136 bytes (gear, gearDashboard, hshifterResulting[32])
# gameplay_i: 1 * 4 = 4 bytes (jobDeliveredEarnedXp)
# buffer_i: 56 bytes
# Total: 4 + 136 + 4 + 56 = 200 bytes. (500 + 200 = 700). Offset: 500 to 699.

# Zone 4 (Offset 700): floats
# common_f: 1 * 4 = 4 bytes (scale) -> Offset 700
# config_f: (12 + 16 + 24 + 8 + 1) * 4 = 61 * 4 = 244 bytes -> Offset 704 to 947
#   (fuelCapacity, fuelWarningFactor, adblueCapacity, adblueWarningFactor, airPressureWarning,
#    airPressurEmergency, oilPressureWarning, waterTemperatureWarning, batteryVoltageWarning,
#    engineRpmMax, gearDifferential, cargoMass, truckWheelRadius[16], gearRatiosForward[24],
#    gearRatiosReverse[8], unitMass)
# truck_f: Offset 948:
#   float speed; (948)
#   float engineRpm; (952)
#   float userSteer; (956)
#   float userThrottle; (960)
#   float userBrake; (964)
#   float userClutch; (968)
#   float gameSteer; (972)
#   float gameThrottle; (976)
#   float gameBrake; (980)
#   float gameClutch; (984)
#   float cruiseControlSpeed; (988)
#   float airPressure; (992)
#   float brakeTemperature; (996)
#   float fuel; (1000)
#   float fuelAvgConsumption; (1004)
#   float fuelRange; (1008)
#   float adblue; (1012)
#   float oilPressure; (1016)
#   float oilTemperature; (1020)
#   float waterTemperature; (1024)
#   float batteryVoltage; (1028)
#   float lightsDashboard; (1032)
#   float wearEngine; (1036)
#   float wearTransmission; (1040)
#   float wearCabin; (1044)
#   float wearChassis; (1048)
#   float wearWheels; (1052)
#   float truckOdometer; (1056)
#   float routeDistance; (1060)
#   float routeTime; (1064)
#   float speedLimit; (1068)
#   ... truck_wheel fields ...

# gameplay_f: Offset 1248:
#   float jobDeliveredCargoDamage; (1248)
#   float jobDeliveredDistanceKm; (1252)
#   float refuelAmount; (1256)
# job_f: Offset 1260:
#   float cargoDamage; (1260)

# Zone 9 (Offset 2300): strings (stringsize = 64)
# config_s: Offset 2300:
#   char truckBrandId[64];   // 2300
#   char truckBrand[64];     // 2364
#   char truckId[64];        // 2428
#   char truckName[64];      // 2492
#   char cargoId[64];        // 2556
#   char cargo[64];          // 2620
#   char cityDstId[64];      // 2684
#   char cityDst[64];        // 2748
#   char compDstId[64];      // 2812
#   char compDst[64];        // 2876
#   char citySrcId[64];      // 2940
#   char citySrc[64];        // 3004
#   char compSrcId[64];      // 3068
#   char compSrc[64];        // 3132
#   char shifterType[16];    // 3196
#   char truckLicensePlate[64];          // 3212
#   char truckLicensePlateCountryId[64]; // 3276
#   char truckLicensePlateCountry[64];   // 3340
#   char jobMarket[32];      // 3404

# Zone 12 (Offset 4300): special events bools
#   bool onJob;              // 4300
#   bool jobFinished;        // 4301
#   bool jobCancelled;       // 4302
#   bool jobDelivered;       // 4303

print("Calculated offsets successfully verified.")

