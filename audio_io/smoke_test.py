import sounddevice as sd
import numpy as np
import time
import queue

def main():
    print("Available Audio Devices:")
    print(sd.query_devices())
    
    # Identify WASAPI host API
    wasapi_hostapi = None
    for api in sd.query_hostapis():
        if 'Windows WASAPI' in api['name']:
            wasapi_hostapi = api['index']
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
    print(f"\nTargeting Device: [{target_device}] {device_info['name']}")

    # Use WASAPI Exclusive mode for lowest latency
    extra_settings = sd.WasapiSettings(exclusive=True)
    
    buffer_sizes = [128, 256, 512]
    duration = 5.0  # seconds
    
    print("\nStarting smoke test...")
    print(f"Get your guitar ready to strum! Each block size will run for {duration} seconds.\n")
    
    for blocksize in buffer_sizes:
        print(f"=== Testing blocksize: {blocksize} samples ===")
        xruns = 0
        q = queue.Queue()
        
        def audio_callback(indata, frames, time_info, status):
            nonlocal xruns
            if status:
                xruns += 1
            # Calculate RMS of the block
            # indata is a numpy array of shape (frames, channels)
            rms = np.sqrt(np.mean(indata**2))
            q.put((rms, status))

        try:
            with sd.InputStream(
                device=target_device, 
                channels=1, 
                samplerate=44100, 
                blocksize=blocksize,
                extra_settings=extra_settings,
                callback=audio_callback
            ):
                start_time = time.time()
                last_print_time = start_time
                
                while time.time() - start_time < duration:
                    while not q.empty():
                        rms, status = q.get()
                        current_time = time.time()
                        # Print RMS roughly every ~100ms
                        if current_time - last_print_time >= 0.1:
                            status_msg = f" [STATUS WARNING: {status}]" if status else ""
                            # Format RMS as a simple text meter for visual feedback
                            meter_len = int(rms * 100) # Simple scaling for visual meter
                            meter = "|" + "#" * min(meter_len, 40)
                            print(f"RMS: {rms:.4f} {meter:<41}{status_msg}")
                            last_print_time = current_time
                    time.sleep(0.01)
                    
            print(f"--- Blocksize {blocksize} test complete ---")
            if xruns == 0:
                print(f"Result: SUCCESS (0 dropouts/xruns recorded)\n")
            else:
                print(f"Result: FAILED ({xruns} dropouts/xruns recorded)\n")
                
        except Exception as e:
            print(f"Failed to initialize stream with blocksize {blocksize}: {e}\n")

if __name__ == "__main__":
    main()
