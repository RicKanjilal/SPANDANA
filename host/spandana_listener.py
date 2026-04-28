"""
SPANDANA — Plant Stress Signal Detector
Host-side listener for Arduino Uno firmware.

Reads serial frames from the Uno, maintains an adaptive EMA baseline
on the piezo signal, flags statistical anomalies as events, classifies
each event by inspecting the context sensors, and live-plots all five
channels with event markers.

Frame format expected from Uno:
    P,raw,delta,moisture,temp,humidity,ldr

Run:
    pip install pyserial numpy matplotlib
    python spandana_listener.py

Adjust PORT below for your system:
    Windows : COM3, COM4, ...
    Linux   : /dev/ttyUSB0, /dev/ttyACM0
    macOS   : /dev/cu.usbmodem*

Author : Ric Kanjilal, Grade 10, Don Bosco School, Liluah
Project: SPANDANA — YIP 2025–26 (Top 30 of 3,300+, IIT Kharagpur)
License: MIT
"""

import collections
import threading
import time

import matplotlib.pyplot as plt
import numpy as np
import serial

# ================= CONFIG =================
PORT = "COM3"
BAUD = 115200

MAX_POINTS = 3000
EMA_ALPHA = 0.02
EVENT_COOLDOWN = 0.4    # seconds between events
DEV_MULTIPLIER = 3.0    # adaptive sensitivity
MIN_STD = 5             # avoids zero sensitivity
# ==========================================

time_buf = collections.deque(maxlen=MAX_POINTS)
piezo_buf = collections.deque(maxlen=MAX_POINTS)
moisture_buf = collections.deque(maxlen=MAX_POINTS)
temp_buf = collections.deque(maxlen=MAX_POINTS)
hum_buf = collections.deque(maxlen=MAX_POINTS)
ldr_buf = collections.deque(maxlen=MAX_POINTS)

events = []
event_labels = []

lock = threading.Lock()
start_time = time.time()
last_event_time = 0

ema_baseline = None
std_window = collections.deque(maxlen=50)


def classify_event(dev, m_now, m_prev, t_now, t_prev, l_now, l_prev):
    """
    Rule-based classifier: looks at the context sensors at the moment
    an anomaly fires and assigns a stress category.

    Deliberately simple. The whole point of SPANDANA's writeup is that
    a richer classifier needs labelled multi-species data and ML —
    which a single school-lab setup cannot produce.
    """
    if m_now > 500:
        return "Chronic Dehydration Stress"
    if m_now < m_prev - 100:
        return "Rehydration Response"
    if t_now > t_prev + 2:
        return "Thermal Stress"
    if abs(l_now - l_prev) > 120:
        return "Light Shock Stress"
    return "Mechanical / Unknown Stress"


def serial_reader():
    global ema_baseline, last_event_time

    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    print("[CONNECTED]")

    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            parts = line.split(",")

            # Expected: P,raw,delta,moisture,temp,humidity,ldr
            if parts[0] != "P" or len(parts) != 7:
                continue

            raw = int(parts[1])
            moisture = int(parts[3])
            temp = float(parts[4])
            hum = float(parts[5])
            ldr = int(parts[6])

            t = time.time() - start_time

            with lock:
                time_buf.append(t)
                piezo_buf.append(raw)
                moisture_buf.append(moisture)
                temp_buf.append(temp)
                hum_buf.append(hum)
                ldr_buf.append(ldr)

                # ---------- Adaptive EMA baseline ----------
                # Plants don't have a fixed "normal". Activity drifts
                # with day/night, humidity, recent stimulus. The EMA
                # tracks the slowly-moving resting state of the signal.
                if ema_baseline is None:
                    ema_baseline = raw
                ema_baseline = (1 - EMA_ALPHA) * ema_baseline + EMA_ALPHA * raw

                # ---------- Deviation & adaptive threshold ----------
                # Threshold = 3 standard deviations of the recent
                # deviation history. When the plant gets noisier, the
                # threshold rises with it — only true outliers fire.
                dev = abs(raw - ema_baseline)
                std_window.append(dev)
                std = np.std(std_window) if len(std_window) > 10 else MIN_STD
                threshold = max(MIN_STD, std * DEV_MULTIPLIER)

                # ---------- Event detection ----------
                # Cooldown prevents a single physical disturbance
                # from registering as dozens of events as the signal
                # rings. 0.4s landed empirically.
                if dev > threshold and (t - last_event_time) > EVENT_COOLDOWN:
                    last_event_time = t

                    m_prev = moisture_buf[-2] if len(moisture_buf) > 1 else moisture
                    t_prev = temp_buf[-2] if len(temp_buf) > 1 else temp
                    l_prev = ldr_buf[-2] if len(ldr_buf) > 1 else ldr

                    label = classify_event(
                        dev, moisture, m_prev, temp, t_prev, ldr, l_prev
                    )

                    events.append(t)
                    event_labels.append(label)

                    print(f"[EVENT] {label} | Δ={dev:.2f}")

        except Exception as e:
            print("[ERROR]", e)


# ================= START READER THREAD =================
threading.Thread(target=serial_reader, daemon=True).start()

# ================= LIVE PLOT =================
plt.ion()
fig, ax = plt.subplots(5, 1, figsize=(14, 10), sharex=True)
fig.suptitle("SPANDANA — Live Plant Signal Monitor", fontsize=14)

while True:
    with lock:
        if len(time_buf) < 50:
            plt.pause(0.05)
            continue

        t = np.array(time_buf)

        ax[0].clear()
        ax[0].plot(t, piezo_buf, color="black", linewidth=0.7)
        ax[0].set_ylabel("Piezo")
        for e in events[-20:]:
            ax[0].axvline(e, color="green", alpha=0.3)

        ax[1].clear()
        ax[1].plot(t, moisture_buf, color="#1f77b4")
        ax[1].set_ylabel("Moisture")

        ax[2].clear()
        ax[2].plot(t, temp_buf, color="#d62728")
        ax[2].set_ylabel("Temp °C")

        ax[3].clear()
        ax[3].plot(t, hum_buf, color="#2ca02c")
        ax[3].set_ylabel("Humidity")

        ax[4].clear()
        ax[4].plot(t, ldr_buf, color="#ff7f0e")
        ax[4].set_ylabel("LDR")
        ax[4].set_xlabel("Time (s)")

    plt.pause(0.05)
