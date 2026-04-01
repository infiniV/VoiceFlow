import numpy as np
import sounddevice as sd
from typing import Optional, Callable
import threading
import queue
from services.logger import get_logger

log = get_logger("audio")


class AudioService:
    TARGET_SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1  # Mono
    DTYPE = np.float32

    def __init__(self):
        self._recording = False
        self._audio_queue = queue.Queue()
        self._audio_data = []
        self._stream: Optional[sd.InputStream] = None
        self._amplitude_callback: Optional[Callable[[float], None]] = None
        self._device_id: Optional[int] = None  # None = default device
        self._actual_sample_rate: int = self.TARGET_SAMPLE_RATE

    def set_device(self, device_id: Optional[int]):
        """Set the input device to use. None for default."""
        self._device_id = device_id
        log.info("Audio device set", device_id=device_id)

    def set_amplitude_callback(self, callback: Callable[[float], None]):
        """Set callback to receive amplitude values for visualization."""
        self._amplitude_callback = callback

    def _audio_callback(self, indata, frames, time, status):
        if status:
            log.warning("Audio status warning", status=str(status))

        # Copy audio data
        audio_chunk = indata.copy().flatten()
        self._audio_queue.put(audio_chunk)

        # Calculate amplitude for visualization using RMS (root mean square)
        if self._amplitude_callback:
            # RMS gives better representation of perceived loudness
            rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
            # Scale to 0-1 range (typical speech RMS is 0.01-0.1 for float32)
            # Multiply by 10 and clamp to make it more visible
            amplitude = min(1.0, rms * 10)
            self._amplitude_callback(amplitude)

    def start_recording(self):
        if self._recording:
            return

        self._recording = True
        self._audio_data = []

        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        log.info("Starting recording", device_id=self._device_id)

        # Try 16kHz first (Whisper's native rate), fall back to device default
        self._actual_sample_rate = self.TARGET_SAMPLE_RATE
        try:
            self._stream = sd.InputStream(
                samplerate=self.TARGET_SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                callback=self._audio_callback,
                blocksize=1024,
                device=self._device_id,
            )
        except sd.PortAudioError:
            device_info = sd.query_devices(self._device_id, 'input')
            fallback_rate = int(device_info['default_samplerate'])
            log.warning("16kHz not supported, using device default",
                        fallback_rate=fallback_rate)
            self._actual_sample_rate = fallback_rate
            self._stream = sd.InputStream(
                samplerate=fallback_rate,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                callback=self._audio_callback,
                blocksize=1024,
                device=self._device_id,
            )
        self._stream.start()
        log.debug("Recording started", sample_rate=self._actual_sample_rate)

    def stop_recording(self) -> np.ndarray:
        if not self._recording:
            return np.array([], dtype=self.DTYPE)

        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Collect all audio from queue
        while not self._audio_queue.empty():
            try:
                chunk = self._audio_queue.get_nowait()
                self._audio_data.append(chunk)
            except queue.Empty:
                break

        if not self._audio_data:
            return np.array([], dtype=self.DTYPE)

        # Concatenate all chunks
        audio = np.concatenate(self._audio_data)
        self._audio_data = []

        # Resample to 16kHz if recorded at a different rate
        if self._actual_sample_rate != self.TARGET_SAMPLE_RATE:
            ratio = self.TARGET_SAMPLE_RATE / self._actual_sample_rate
            new_length = int(len(audio) * ratio)
            indices = np.linspace(0, len(audio) - 1, new_length)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(self.DTYPE)
            log.debug("Resampled audio",
                      from_rate=self._actual_sample_rate,
                      to_rate=self.TARGET_SAMPLE_RATE,
                      samples=new_length)

        return audio

    def is_recording(self) -> bool:
        return self._recording

    @staticmethod
    def get_input_devices() -> list:
        """Get list of available input devices."""
        devices = sd.query_devices()
        input_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                })
        return input_devices
