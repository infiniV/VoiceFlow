"""
GPU detection and management for Dictore.

Uses ctranslate2's built-in functions to detect CUDA availability
without requiring torch dependency.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from services.logger import get_logger

log = get_logger("gpu")

# Device options for settings
DEVICE_OPTIONS = ["auto", "cpu", "cuda"]

# Compute type mappings
CPU_COMPUTE_TYPE = "int8"
CUDA_COMPUTE_TYPE = "float16"

# cuDNN DLLs required for CUDA inference (Windows)
CUDNN_DLLS = [
    "cudnn_ops64_9.dll",
    "cudnn_cnn64_9.dll",
]

# Cache for CUDA availability check result
_cuda_available_cache: Optional[bool] = None
_cudnn_path_added: bool = False
_nvidia_preloaded: bool = False


def _preload_nvidia_libs() -> None:
    """
    On Linux, pre-load CUDA shared libraries shipped by the nvidia-* pip
    packages (e.g. nvidia-cublas-cu12) using RTLD_GLOBAL so ctranslate2's
    dlopen("libcublas.so.12") resolves them.

    The nvidia pip packages stash .so files under
    site-packages/nvidia/<pkg>/lib/, which is not on the dynamic linker's
    default search path. ctranslate2 4.x has no Linux-side init code that
    fixes this, so libcublas appears unloadable at runtime — both in the
    venv and in the PyInstaller-bundled AppImage (when --collect-all=nvidia
    is used to ship the packages).

    Pre-loading every .so under each nvidia/<pkg>/lib/ directory makes the
    symbols globally visible, which is what subsequent dlopen() calls
    inside libctranslate2 actually need.

    No-op on non-Linux platforms and when the nvidia namespace isn't
    importable.
    """
    global _nvidia_preloaded
    if _nvidia_preloaded:
        return
    _nvidia_preloaded = True

    if sys.platform == "win32":
        return

    try:
        import nvidia  # namespace package created by nvidia-* pip wheels
    except ImportError:
        return

    import ctypes
    paths = list(getattr(nvidia, "__path__", []))
    if not paths:
        return

    nvidia_root = paths[0]
    for pkg in os.listdir(nvidia_root):
        lib_dir = os.path.join(nvidia_root, pkg, "lib")
        if not os.path.isdir(lib_dir):
            continue
        for so in os.listdir(lib_dir):
            if ".so" not in so:
                continue
            so_path = os.path.join(lib_dir, so)
            try:
                ctypes.CDLL(so_path, mode=ctypes.RTLD_GLOBAL)
            except OSError as e:
                log.debug("Failed to preload nvidia lib", lib=so, error=str(e))


# Preload on first import so libcublas etc. are resolvable for the rest
# of the module's lifetime, including the _check_cudnn_available() probe.
_preload_nvidia_libs()


def _get_local_cuda_dir() -> Path:
    """Get the local CUDA directory where we store downloaded cuDNN."""
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    else:
        base = Path.home()
    return base / ".Dictore" / "cuda"


def _add_local_cudnn_to_path():
    """Add local cuDNN directory to PATH if it exists."""
    global _cudnn_path_added
    if _cudnn_path_added:
        return

    cuda_dir = _get_local_cuda_dir()
    if cuda_dir.exists():
        cuda_str = str(cuda_dir)
        current_path = os.environ.get("PATH", "")
        if cuda_str not in current_path:
            os.environ["PATH"] = cuda_str + os.pathsep + current_path
            log.debug("Added local cuDNN to PATH", path=cuda_str)
    _cudnn_path_added = True


@dataclass
class GpuInfo:
    """Information about GPU availability and status."""
    cuda_available: bool
    device_count: int
    gpu_name: Optional[str]
    supported_compute_types: list[str]
    current_device: str
    current_compute_type: str


def _check_cudnn_available() -> tuple[bool, Optional[str]]:
    """
    Check if cuDNN libraries are available.

    Returns:
        Tuple of (is_available, error_message)
    """
    if sys.platform != "win32":
        # On Linux, verify that libcublas is actually loadable at runtime.
        # ctranslate2 can detect CUDA device presence without libcublas, but
        # inference will fail if the library isn't available.
        import ctypes
        for lib_name in ("libcublas.so.12", "libcublas.so.11", "libcublas.so"):
            try:
                ctypes.CDLL(lib_name)
                return True, None
            except OSError:
                continue
        log.warning("libcublas not loadable on Linux, CUDA disabled")
        return False, "CUDA libraries not found. Install nvidia-cuda-toolkit or use CPU mode."

    # First, add local cuDNN to PATH if it exists
    _add_local_cudnn_to_path()

    # On Windows, check for cuDNN DLLs in PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    # Also check our local cuDNN directory
    local_cuda = _get_local_cuda_dir()
    if local_cuda.exists():
        path_dirs.insert(0, str(local_cuda))

    # Also check common CUDA locations
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path:
        path_dirs.append(os.path.join(cuda_path, "bin"))

    # Check Program Files for CUDA
    for pf in ["C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA",
               "C:\\Program Files\\NVIDIA\\CUDNN"]:
        if os.path.exists(pf):
            for version_dir in os.listdir(pf) if os.path.isdir(pf) else []:
                bin_path = os.path.join(pf, version_dir, "bin")
                if os.path.exists(bin_path):
                    path_dirs.append(bin_path)

    missing_dlls = []
    for dll in CUDNN_DLLS:
        found = False
        for dir_path in path_dirs:
            if os.path.exists(os.path.join(dir_path, dll)):
                found = True
                break
        if not found:
            missing_dlls.append(dll)

    if missing_dlls:
        error = f"cuDNN not installed. Click 'Download' to enable GPU acceleration."
        log.warning("cuDNN not available", missing=missing_dlls)
        return False, error

    log.debug("cuDNN libraries found")
    return True, None


def is_cuda_available() -> bool:
    """
    Check if CUDA is available and usable (including cuDNN).

    Returns True if CUDA device is usable, False otherwise.
    """
    global _cuda_available_cache

    # Return cached result if available
    if _cuda_available_cache is not None:
        return _cuda_available_cache

    try:
        import ctranslate2
        compute_types = ctranslate2.get_supported_compute_types("cuda")
        cuda_detected = len(compute_types) > 0

        if not cuda_detected:
            log.debug("CUDA not detected by ctranslate2")
            _cuda_available_cache = False
            return False

        log.debug("CUDA detected by ctranslate2", compute_types=list(compute_types))

        # Check for cuDNN libraries
        cudnn_available, cudnn_error = _check_cudnn_available()
        if not cudnn_available:
            log.warning("CUDA detected but cuDNN not available", error=cudnn_error)
            _cuda_available_cache = False
            return False

        log.debug("CUDA availability check passed", available=True, compute_types=list(compute_types))
        _cuda_available_cache = True
        return True

    except Exception as e:
        log.debug("CUDA not available", error=str(e))
        _cuda_available_cache = False
        return False


def get_cuda_compute_types() -> list[str]:
    """
    Get list of supported compute types for CUDA.

    Returns empty list if CUDA is not available.
    """
    try:
        import ctranslate2
        return list(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        return []


def get_cpu_compute_types() -> list[str]:
    """Get list of supported compute types for CPU."""
    try:
        import ctranslate2
        return list(ctranslate2.get_supported_compute_types("cpu"))
    except Exception:
        return ["int8", "int8_float32", "float32"]


def get_gpu_name() -> Optional[str]:
    """
    Get GPU name using nvidia-smi.

    Returns None if nvidia-smi is not available or fails.
    """
    try:
        # Use CREATE_NO_WINDOW flag on Windows to prevent console popup
        creationflags = 0
        try:
            creationflags = subprocess.CREATE_NO_WINDOW
        except AttributeError:
            pass  # Not on Windows

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creationflags
        )
        if result.returncode == 0:
            # Return first GPU name (multi-GPU systems return multiple lines)
            names = result.stdout.strip().split('\n')
            gpu_name = names[0] if names else None
            log.debug("GPU name detected", name=gpu_name)
            return gpu_name
    except FileNotFoundError:
        log.debug("nvidia-smi not found")
    except subprocess.TimeoutExpired:
        log.debug("nvidia-smi timed out")
    except Exception as e:
        log.debug("Failed to get GPU name", error=str(e))
    return None


def get_gpu_count() -> int:
    """
    Get number of CUDA devices.

    Returns 0 if CUDA is not available.
    """
    if not is_cuda_available():
        return 0

    try:
        creationflags = 0
        try:
            creationflags = subprocess.CREATE_NO_WINDOW
        except AttributeError:
            pass

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creationflags
        )
        if result.returncode == 0:
            return len(result.stdout.strip().split('\n'))
    except Exception:
        pass

    # Fallback: if CUDA is available, assume at least 1 GPU
    return 1


def resolve_device(device_preference: str) -> str:
    """
    Resolve device preference to actual device.

    Args:
        device_preference: "auto", "cpu", or "cuda"

    Returns:
        "cpu" or "cuda" based on availability
    """
    if device_preference == "cpu":
        return "cpu"
    elif device_preference == "cuda":
        if is_cuda_available():
            return "cuda"
        else:
            log.warning("CUDA requested but not available, falling back to CPU")
            return "cpu"
    else:  # "auto"
        if is_cuda_available():
            log.info("Auto-detected CUDA, using GPU")
            return "cuda"
        else:
            log.info("CUDA not available, using CPU")
            return "cpu"


def get_compute_type(device: str) -> str:
    """
    Get the optimal compute type for a device.

    Args:
        device: "cpu" or "cuda"

    Returns:
        Appropriate compute_type string
    """
    if device == "cuda":
        cuda_types = get_cuda_compute_types()
        if CUDA_COMPUTE_TYPE in cuda_types:
            return CUDA_COMPUTE_TYPE
        elif "int8_float16" in cuda_types:
            return "int8_float16"
        elif cuda_types:
            return cuda_types[0]
        else:
            return CPU_COMPUTE_TYPE  # Fallback
    else:
        return CPU_COMPUTE_TYPE


def validate_device_setting(device: str) -> tuple[bool, Optional[str]]:
    """
    Validate that a device setting is usable.

    Args:
        device: Device preference ("auto", "cpu", "cuda")

    Returns:
        Tuple of (is_valid, error_message)
    """
    if device not in DEVICE_OPTIONS:
        return False, f"Invalid device option: {device}"

    if device == "cuda":
        if not is_cuda_available():
            # Check why CUDA is not available
            try:
                import ctranslate2
                compute_types = ctranslate2.get_supported_compute_types("cuda")
                if len(compute_types) > 0:
                    # CUDA detected but cuDNN missing
                    return False, "CUDA detected but cuDNN is not installed. Install cuDNN 9.x or use CPU mode."
            except Exception:
                pass
            return False, "CUDA is not available. Please install NVIDIA drivers and CUDA toolkit."

    return True, None


def get_cudnn_status() -> tuple[bool, Optional[str]]:
    """
    Get cuDNN installation status for display in UI.

    Returns:
        Tuple of (is_available, status_message)
    """
    available, error = _check_cudnn_available()
    if available:
        return True, "cuDNN installed"
    else:
        return False, error or "cuDNN not found"


def reset_cuda_cache():
    """Reset the CUDA availability cache to force re-detection."""
    global _cuda_available_cache, _cudnn_path_added
    _cuda_available_cache = None
    _cudnn_path_added = False
    log.debug("CUDA cache reset")


def has_nvidia_gpu() -> bool:
    """
    Check if NVIDIA GPU is present (even if cuDNN is not installed).
    Used to determine if we should offer cuDNN download.
    """
    try:
        import ctranslate2
        compute_types = ctranslate2.get_supported_compute_types("cuda")
        return len(compute_types) > 0
    except Exception:
        return False
