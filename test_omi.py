import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import struct
import math

load_dotenv()

from omi import listen_to_omi

now = datetime.now()
time_now = now.strftime("%H:%M:%S")
date_now = now.strftime("%A, %B %d, %Y")

DEVICE_ID = "046AC44C-4ED2-67B2-586E-71E710920E2C"
OMI_CHAR_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"

def current_date_and_time():
    print(f"\nAll good at {time_now} on {date_now}.")

def calculate_rms_amplitude(pcm_data):
    """Calculate RMS (Root Mean Square) amplitude from 16-bit PCM data"""
    if len(pcm_data) < 2:
        return 0
    
    # Convert bytes to 16-bit signed integers
    num_samples = len(pcm_data) // 2
    samples = struct.unpack(f'<{num_samples}h', pcm_data)
    
    # Calculate RMS
    sum_squares = sum(s * s for s in samples)
    rms = math.sqrt(sum_squares / num_samples)
    
    # Normalize to 0-100 scale (max 16-bit value is 32768)
    normalized = (rms / 32768.0) * 100
    
    return normalized

def calculate_peak_amplitude(pcm_data):
    """Calculate peak amplitude from 16-bit PCM data"""
    if len(pcm_data) < 2:
        return 0
    
    # Convert bytes to 16-bit signed integers
    num_samples = len(pcm_data) // 2
    samples = struct.unpack(f'<{num_samples}h', pcm_data)
    
    # Find peak
    peak = max(abs(s) for s in samples)
    
    # Normalize to 0-100 scale
    normalized = (peak / 32768.0) * 100
    
    return normalized

def display_amplitude_bar(amplitude, label="Volume"):
    """Display a visual bar for amplitude"""
    bar_length = 50
    filled = int(amplitude / 100 * bar_length)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r{label}: [{bar}] {amplitude:.1f}%", end='', flush=True)

async def main():
    print("Monitoring audio amplitude from Omi device...")
    print("Format: 8kHz, 16-bit PCM, mono\n")
    
    packet_count = 0
    
    def handle_audio(sender, data):
        nonlocal packet_count
        packet_count += 1
        
        if isinstance(data, bytearray):
            data = bytes(data)
        
        # Skip 1 byte header, rest is 16-bit PCM at 8kHz
        pcm_data = data[1:]
        
        # Calculate both RMS and peak amplitude
        rms = calculate_rms_amplitude(pcm_data)
        peak = calculate_peak_amplitude(pcm_data)
        
        # Display RMS (better for general loudness)
        display_amplitude_bar(rms, f"RMS (packet {packet_count})")
    
    print("🎙️  Speak into your Omi device to see amplitude\n")
    
    try:
        await listen_to_omi(DEVICE_ID, OMI_CHAR_UUID, handle_audio)
    except KeyboardInterrupt:
        print("\n\nStopped monitoring")

if __name__ == "__main__":
    current_date_and_time()
    asyncio.run(main())