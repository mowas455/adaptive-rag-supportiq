# NexCart Product Troubleshooting Guide

This guide covers the NexCart Basics hardware line: the PulseBuds wireless earbuds, HomePlug mini smart plugs, LockStep smart deadbolt, and GlowBar LED light strip. Keep the device nearby. Most issues are firmware, power, or pairing related.

## PulseBuds will not pair

1. Place both earbuds in the case, close the lid for 10 seconds, then open it. The case LED should pulse white.
2. On your phone, forget the previous "NexCart PulseBuds" Bluetooth entry.
3. Press and hold the case button for 8 seconds until the LED flashes blue. That is pairing mode.
4. Connect from Bluetooth settings. Do not use Fast Pair prompts from a previous session.

If only one earbud plays audio, reset the pair: both buds in the case, hold the case button 15 seconds until the LED turns amber, then pair again. Firmware 2.4.1 (January 2026) fixed a left-bud mute bug after iOS 18.4; update through the NexCart app under **Devices → PulseBuds → Firmware**.

Battery drain overnight usually means the case lid magnet is not seating. Clean the charging pins with a dry cotton swab. Do not use alcohol on the mesh.

## HomePlug mini does not appear in the app

HomePlug requires 2.4 GHz Wi-Fi. 5 GHz-only networks will fail silently. Create a 2.4 GHz SSID or enable band steering compatibility. The plug LED should blink amber during setup and turn solid green when joined.

If the LED is red, the plug cannot reach your router. Move it closer for first pairing, then use the app's "Relocate" flow. Factory reset: hold the side button 12 seconds until the LED blinks red-green.

Do not connect HomePlug to space heaters, window AC units, or devices over 10A. The thermal cutoff will trip and the LED will blink red twice. Unplug for 5 minutes to reset. Repeated trips void the warranty.

## LockStep deadbolt will not auto-unlock

Auto-unlock needs Bluetooth plus location permission set to **Always** on iOS/Android. Geofence radius is 30 meters. If you live in a dense apartment, reduce the radius to 15 meters in **Devices → LockStep → Geofence** to avoid unlocking in the hallway.

After a deadbolt replacement or door strike adjustment, recalibrate: open the app, **Calibrate motor**, and run the door through lock/unlock twice. A grinding sound means the strike plate is misaligned; stop and use the mechanical key. Continuing can burn the motor.

LockStep stores 50 PIN codes and 10 scheduled guest codes. Guest codes expire at the time you set; they cannot be extended—create a new code. If the keypad is unresponsive in cold weather (below 20°F / −6°C), warm the unit for a minute; this is a known limitation, not a defect.

Battery pack: four AA lithium batteries last about 8 months. Alkaline batteries last 4–5 months and may fail in winter. Low-battery chirps start at 20%. Replace both pairs together. Do not mix chemistries.

## GlowBar LED strip flickers or shows the wrong color

Flicker on dim scenes is usually an overloaded USB-C power adapter. Use the included 24W adapter, not a phone charger. Addressable color errors (one segment stuck green) often mean a kinked data line. Unplug, straighten the strip, and power-cycle.

The strip supports Matter over Wi-Fi on firmware 1.8+. If Matter pairing fails, remove the accessory from Apple Home / Google Home first, then retry from the NexCart app **Works with**.

## Still stuck?

Collect the device serial (inside the battery door or on the QR card), app version, and phone OS. Open **Help → Hardware ticket**. Hardware replacements for manufacturing defects are processed under the 12-month Basics warranty, not the 15-day electronics return window.
