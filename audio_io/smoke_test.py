import sounddevice as sd
import numpy as np
import time
import queue

def main():
    print("Available Audio Devices:")
    print(sd.query_devices())
    
    # Identify WASAPI host API
    wasapi_hostapi = None
    for idx, api in enumerate(sd.query_hostapis()):
        if 'Windows WASAPI' in api['name']:
            wasapi_hostapi = idx
            break
            
    if wasapi_hostapi is None:
        print("\nError: WASAPI host API not found on this system.")
        return

    # Find the Komplete Audio 1 WASAPI device
    target_device = None
    for idx, d in enumerate(sd.query_devices()):
        if d['hostapi'] == wasapi_hostapi and 'Komplete Audio' in d['name'] and d['max_input_channels'] > 0:
            target_device = idx
            break
            
    if target_device is None:
        print("\nWarning: Could not find 'Komplete Audio 1' WASAPI input device.")
        print("Available WASAPI input devices:")
        for idx, d in enumerate(sd.query_devices()):
            if d['hostapi'] == wasapi_hostapi and d['max_input_channels'] > 0:
                print(f"[{idx}] {d['name']} (In: {d['max_input_channels']})")
        
        # Fallback to the first available WASAPI input device
        for idx, d in enumerate(sd.query_devices()):
            if d['hostapi'] == wasapi_hostapi and d['max_input_channels'] > 0:
                target_device = idx
                print(f"Falling back to WASAPI device [{idx}] {d['name']}")
                break
                
    if target_device is None:
        print("\nError: No WASAPI input devices available.")
        return
        
    device_info = sd.query_devices(target_device)
    default_samplerate = int(device_info['default_samplerate'])
    max_channels = min(int(device_info['max_input_channels']), 2)
    print(f"\nTargeting Device: [{target_device}] {device_info['name']} at {default_samplerate}Hz ({max_channels} channels)")

    # Use WASAPI Exclusive mode for lowest latency
    extra_settings = sd.WasapiSettings(exclusive=True)
    
    buffer_sizes = [128, 256, 512]
    duration = 5.0  # seconds
    
    print("\nStarting smoke test...")
    print(f"Get your guitar ready to strum! We will verify that sound is actively coming in. Each block size will run for {duration} seconds.\n")
    
    for blocksize in buffer_sizes:
        print(f"=== Testing blocksize: {blocksize} samples ===")
        xruns = 0
        q = queue.Queue()
        
        # Track maximum RMS seen to verify sound input
        max_rms = np.zeros(max_channels)
        
        def audio_callback(indata, frames, time_info, status):
            nonlocal xruns
            if status:
                xruns += 1
            # Calculate RMS for each available channel
            # indata is shape (frames, channels)
            rms_vals = []
            for ch in range(max_channels):
                rms_val = np.sqrt(np.mean(indata[:, ch]**2))
                rms_vals.append(rms_val)
                if rms_val > max_rms[ch]:
                    max_rms[ch] = rms_val
            q.put((rms_vals, status))

        try:
            with sd.InputStream(
                device=target_device, 
                channels=max_channels, 
                samplerate=default_samplerate, 
                blocksize=blocksize,
                extra_settings=extra_settings,
                callback=audio_callback
            ):
                start_time = time.time()
                last_print_time = start_time
                
                while time.time() - start_time < duration:
                    while not q.empty():
                        rms_vals, status = q.get()
                        current_time = time.time()
                        # Print RMS roughly every ~100ms
                        if current_time - last_print_time >= 0.1:
                            status_msg = f" [STATUS WARNING: {status}]" if status else ""
                            # Format RMS meters
                            meter_strings = []
                            for ch, rms in enumerate(rms_vals):
                                meter_len = int(rms * 100)
                                meter = "#" * min(meter_len, 20)
                                meter_strings.append(f"Ch{ch}: {rms:.4f} |{meter:<20}|")
                            
                            print("  ".join(meter_strings) + status_msg)
                            last_print_time = current_time
                    time.sleep(0.01)
                    
            print(f"--- Blocksize {blocksize} test complete ---")
            
            # Sound verification threshold
            # A threshold of 0.005 is generally higher than baseline noise
            sound_detected = [max_val > 0.005 for max_val in max_rms]
            
            print("Sound Detection Results:")
            for ch in range(max_channels):
                status_str = f"ACTIVE (Peak RMS: {max_rms[ch]:.4f})" if sound_detected[ch] else f"SILENT (Peak RMS: {max_rms[ch]:.4f})"
                print(f"  Channel {ch}: {status_str}")
            
            if not any(sound_detected):
                print("  [WARNING]: No active audio input detected on any channel! Make sure your instrument is turned up and you strummer/played during the test.")
            
            if xruns == 0:
                print(f"Latency/Buffer Result: SUCCESS (0 dropouts/xruns recorded)\n")
            else:
                print(f"Latency/Buffer Result: FAILED ({xruns} dropouts/xruns recorded)\n")
                
        except Exception as e:
            print(f"Failed to initialize stream with blocksize {blocksize}: {e}\n")

if __name__ == "__main__":
    main()
