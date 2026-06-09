"""Audio-source seam.

`AudioSource` is a small protocol so the recorder can be driven by:
  * Production: `SoundDeviceAudioSource` (added in slices 4/5 — Windows WASAPI
    loopback, Linux monitor sources, mic via sounddevice).
  * Tests: `FakeAudioSource` (synchronous, deterministic — tests `push()`
    frames; the recorder consumes them via the registered callback).

The contract is intentionally tiny: start with a frame callback, deliver mono
float32 ndarrays at the declared sample rate, stop on request.
"""

from __future__ import annotations

import numpy as np
from typing import Callable, Optional, Protocol

FrameCallback = Callable[[np.ndarray], None]


class AudioSource(Protocol):
    sample_rate: int
    channels: int

    def start(self, on_frames: FrameCallback) -> None: ...
    def stop(self) -> None: ...


class FakeAudioSource:
    """Test double. Push frames manually; the registered callback receives them."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.channels = 1
        self._callback: Optional[FrameCallback] = None
        self._stopped = False

    def start(self, on_frames: FrameCallback) -> None:
        self._callback = on_frames
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
        self._callback = None

    def push(self, frames: np.ndarray) -> None:
        """Deliver a block of frames to the recorder as if from the audio thread."""
        if self._stopped or self._callback is None:
            return
        if frames.dtype != np.float32:
            frames = frames.astype(np.float32, copy=False)
        self._callback(frames)


class SoundDeviceAudioSource:
    """Production AudioSource backed by sounddevice.

    `loopback=True` on Windows + WASAPI engages WasapiSettings(loopback=True);
    on Linux the loopback flag is ignored — the caller picks a `.monitor`
    device id directly.

    Sample-rate handling: many PortAudio backends (notably JACK and strict
    ALSA setups) refuse to open a stream at an arbitrary rate. We always try
    the target rate first, then fall back to the device's native default rate
    and resample on-the-fly with `np.interp`. Whisper is robust to the small
    quality hit from linear resampling; nobody is going to ABX a meeting
    transcript against the 48 kHz original.
    """

    def __init__(
        self,
        device_id: int,
        sample_rate: int = 16000,
        loopback: bool = False,
        blocksize: int = 1024,
    ) -> None:
        self.sample_rate = sample_rate  # output rate (what the recorder expects)
        self.channels = 1
        self._device_id = device_id
        self._loopback = loopback
        self._blocksize = blocksize
        self._stream = None  # sounddevice.InputStream
        self._callback: Optional[FrameCallback] = None
        self._device_rate: Optional[int] = None  # the rate the stream actually opens at
        self._resample_phase: float = 0.0  # carries fractional positions across blocks

    def start(self, on_frames: FrameCallback) -> None:
        import sounddevice as sd  # local import — keep tests free of the C dep
        self._callback = on_frames
        self._resample_phase = 0.0

        extra_settings = None
        if self._loopback:
            wasapi = getattr(sd, "WasapiSettings", None)
            if wasapi is not None:
                try:
                    extra_settings = wasapi(loopback=True)
                except TypeError:
                    extra_settings = None

        # Open the stream at the target rate if possible; otherwise fall back
        # to the device's native rate and resample.
        candidate_rates = [self.sample_rate]
        max_input_channels = 1
        max_output_channels = 0
        try:
            info = sd.query_devices(self._device_id)
            native = int(info.get("default_samplerate") or 0)
            if native > 0 and native not in candidate_rates:
                candidate_rates.append(native)
            max_input_channels = max(1, int(info.get("max_input_channels") or 1))
            max_output_channels = int(info.get("max_output_channels") or 0)
        except Exception:
            pass
        # Common fallbacks if everything else fails.
        for r in (48000, 44100):
            if r not in candidate_rates:
                candidate_rates.append(r)

        # Channel-count fallback. WASAPI loopback / Stereo Mix on Windows
        # captures an OUTPUT device — `sd.query_devices()` reports
        # `max_input_channels = 0` for those, with the real channel count
        # exposed as `max_output_channels` (typically 2). Opening with
        # channels=1 was rejected by PortAudio with
        #   "Invalid number of channels [PaErrorCode -9998]"
        # leaving the meeting recorder with header-only WAV files.
        #
        # The downmix in _make_pa_callback below already flattens N-channel
        # input to mono, so we just need to open the stream at the channel
        # count PortAudio is willing to give us.
        candidate_channels: list[int] = []
        if self._loopback:
            # WASAPI loopback path. Try output channel count first (real
            # answer for speaker-loopback devices), then input channel count
            # (in case the user picked an actual capture device exposed as
            # loopback), then mono as a last resort.
            for cand in (max_output_channels, max_input_channels, 1):
                if cand and cand not in candidate_channels:
                    candidate_channels.append(cand)
        else:
            # Mic: keep prior behavior (mono first), but allow a stereo
            # fallback in case the chosen device refuses mono open.
            candidate_channels.append(1)
            if max_input_channels > 1 and max_input_channels not in candidate_channels:
                candidate_channels.append(max_input_channels)

        last_err: Optional[Exception] = None
        for ch in candidate_channels:
            for rate in candidate_rates:
                try:
                    stream = sd.InputStream(
                        device=self._device_id,
                        samplerate=rate,
                        channels=ch,
                        dtype="float32",
                        blocksize=0,  # let PortAudio pick — JACK in particular dislikes fixed block sizes
                        callback=self._make_pa_callback(rate),
                        extra_settings=extra_settings,
                    )
                    stream.start()
                    self._stream = stream
                    self._device_rate = rate
                    return
                except Exception as exc:
                    last_err = exc
                    continue
        # Nothing worked.
        self._callback = None
        raise RuntimeError(
            f"Could not open audio device {self._device_id}: {last_err}"
        )

    def _make_pa_callback(self, device_rate: int):
        target_rate = self.sample_rate
        do_resample = device_rate != target_rate

        def _cb(indata, _frames, _time, _status):  # noqa: D401 - sd callback
            cb = self._callback
            if cb is None:
                return
            arr = indata
            if arr.ndim == 2 and arr.shape[1] > 1:
                arr = arr.mean(axis=1)
            elif arr.ndim == 2:
                arr = arr[:, 0]
            if arr.dtype != np.float32:
                arr = arr.astype(np.float32, copy=False)
            if do_resample:
                arr = self._resample(arr, device_rate, target_rate)
                if arr.size == 0:
                    return
            cb(arr.copy())  # copy — sounddevice reuses its buffer

        return _cb

    def _resample(self, arr: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """Linear resampling with phase carry-over so successive blocks join
        cleanly. Good enough for speech going into Whisper."""
        if arr.size == 0:
            return arr
        ratio = dst_rate / src_rate
        first = float(self._resample_phase)
        # Highest output index whose input position is still inside this block:
        # we need first + n/ratio <= arr.size - 1, so n <= (arr.size-1-first)*ratio.
        max_n_float = (arr.size - 1 - first) * ratio
        if max_n_float < 0:
            # Phase is past this block's last sample — produce nothing, advance.
            self._resample_phase = first - arr.size
            return np.zeros(0, dtype=np.float32)
        max_n = int(np.floor(max_n_float))  # may be 0 → still emit one sample
        out_idx = np.arange(max_n + 1, dtype=np.float64)
        in_idx = first + out_idx / ratio
        src_idx = np.arange(arr.size, dtype=np.float64)
        out = np.interp(in_idx, src_idx, arr).astype(np.float32)
        # Absolute input position the NEXT output sample would land at, minus
        # this block's size — i.e. how far into the next block to skip.
        next_first = first + (max_n + 1) / ratio
        self._resample_phase = next_first - arr.size
        return out

    def stop(self) -> None:
        self._callback = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._device_rate = None
        self._resample_phase = 0.0


class ParecAudioSource:
    """Linux-only loopback source backed by `parec` (PulseAudio/PipeWire).

    PortAudio on Linux is unreliable for loopback — its ALSA backend can hide
    monitor sources entirely, and its JACK backend renames them by application
    instead of by device. `parec` talks straight to PipeWire / pulse and
    captures the exact `.monitor` source the user picked.
    """

    def __init__(
        self,
        source_name: str,
        sample_rate: int = 16000,
        block_samples: int = 1024,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = 1
        self._source_name = source_name
        self._block_samples = block_samples
        self._proc = None
        self._reader: Optional[object] = None  # threading.Thread when running
        self._stopped = False
        self._callback: Optional[FrameCallback] = None

    def start(self, on_frames: FrameCallback) -> None:
        import shutil
        import subprocess
        import threading
        from services.logger import get_logger

        self._log = get_logger("meeting_audio")

        if shutil.which("parec") is None:
            raise RuntimeError(
                "parec is not installed — required for Linux loopback recording. "
                "Install pulseaudio-utils (pactl/parec ship together)."
            )
        self._callback = on_frames
        self._stopped = False
        # NOTE: do not pass preexec_fn here. We previously used it to set
        # PR_SET_PDEATHSIG so parec would die with the parent — but
        # preexec_fn is documented as unsafe in a multithreaded process
        # (subprocess docs: the child can deadlock before exec if it
        # inherits a held lock from another thread). Dictore has many
        # threads (writer, hotkey, asyncio RPC, transcribe queue, etc.)
        # and that deadlock fired in the field on Bluetooth source
        # selection — wedged the entire asyncio loop and corrupted
        # PipeWire routing. Rely instead on controller.shutdown() (wired
        # to QApplication.aboutToQuit) to kill parec on every normal exit
        # path. Orphan parec on SIGKILL is the accepted trade-off.
        self._proc = subprocess.Popen(
            [
                "parec",
                f"--device={self._source_name}",
                "--raw",
                "--format=float32le",
                f"--rate={self.sample_rate}",
                "--channels=1",
                "--latency-msec=20",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._log.info(
            "parec started",
            source=self._source_name,
            pid=self._proc.pid,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        # Drain stderr in a separate thread so we see why parec died on its own.
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _read_loop(self) -> None:
        block_bytes = self._block_samples * 4  # float32
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        while not self._stopped:
            try:
                data = proc.stdout.read(block_bytes)
            except Exception as exc:
                if hasattr(self, "_log"):
                    self._log.warning("parec read failed", error=str(exc))
                break
            if not data:
                # parec closed its pipe — almost always means the subprocess
                # exited (often because the source went away or pulse refused).
                if hasattr(self, "_log") and not self._stopped:
                    exit_code = proc.poll()
                    self._log.warning(
                        "parec stream ended",
                        exit_code=exit_code,
                        source=self._source_name,
                    )
                break
            cb = self._callback
            if cb is None:
                continue
            arr = np.frombuffer(data, dtype=np.float32)
            if arr.size == 0:
                continue
            cb(arr.copy())

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            for raw in iter(proc.stderr.readline, b""):
                if self._stopped:
                    return
                line = raw.decode("utf-8", "replace").strip()
                if line and hasattr(self, "_log"):
                    self._log.warning("parec stderr", line=line)
        except Exception:
            pass

    def stop(self) -> None:
        self._stopped = True
        self._callback = None
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=1.0)
                except Exception:
                    self._proc.kill()
            except Exception:
                pass
            self._proc = None
