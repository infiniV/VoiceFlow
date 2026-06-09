"""
CUDA libraries auto-downloader.

On Windows: Downloads cuDNN and cuBLAS DLLs from NVIDIA's public CDN to ~/.Dictore/cuda/
On Linux: CUDA libs are provided by nvidia pip packages (cublas etc.) and preloaded at startup.
No login required - uses the redistributable packages.
"""
import os
import sys
import zipfile
import tempfile
import shutil
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from services.logger import get_logger

log = get_logger("cuda")

IS_LINUX = sys.platform.startswith('linux')


@dataclass
class DownloadProgress:
    """Track download progress."""
    downloading: bool = False
    downloaded_bytes: int = 0
    total_bytes: int = 0
    percent: int = 0
    error: Optional[str] = None
    complete: bool = False
    success: bool = False
    status: str = ""  # Current operation status


# Global progress tracker
_download_progress = DownloadProgress()

# NVIDIA cuDNN redistributable URL (public, no login required)
# Using cuDNN 9.x for CUDA 12
CUDNN_VERSION = "9.5.1.17"
CUDNN_CUDA_VERSION = "12"
CUDNN_URL = f"https://developer.download.nvidia.com/compute/cudnn/redist/cudnn/windows-x86_64/cudnn-windows-x86_64-{CUDNN_VERSION}_cuda{CUDNN_CUDA_VERSION}-archive.zip"

# NVIDIA cuBLAS redistributable URL (public, no login required)
CUBLAS_VERSION = "12.8.3.14"
CUBLAS_URL = f"https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/libcublas-windows-x86_64-{CUBLAS_VERSION}-archive.zip"

# Required DLLs for CTranslate2/faster-whisper
REQUIRED_CUDNN_DLLS = [
    "cudnn_ops64_9.dll",
    "cudnn_cnn64_9.dll",
]

# Required cuBLAS DLLs
REQUIRED_CUBLAS_DLLS = [
    "cublas64_12.dll",
    "cublasLt64_12.dll",
]


def get_cuda_dir() -> Path:
    """Get the local CUDA directory for storing cuDNN DLLs."""
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    else:
        base = Path.home()
    return base / ".Dictore" / "cuda"


def _find_nvidia_pip_lib(lib_name: str) -> bool:
    """Check if an nvidia .so lib exists in pip packages (Linux only)."""
    venv_sp = os.path.join(sys.prefix, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
    nvidia_dir = os.path.join(venv_sp, 'nvidia')
    if not os.path.isdir(nvidia_dir):
        return False
    for pkg in os.listdir(nvidia_dir):
        lib_dir = os.path.join(nvidia_dir, pkg, 'lib')
        if os.path.isdir(lib_dir):
            for f in os.listdir(lib_dir):
                if f.startswith(lib_name):
                    return True
    return False


def is_cudnn_installed() -> bool:
    """Check if cuDNN libraries are already installed."""
    if IS_LINUX:
        # On Linux, cuDNN is either bundled in ctranslate2 or not required
        return True

    cuda_dir = get_cuda_dir()
    if not cuda_dir.exists():
        return False

    # Check for the main required cuDNN DLLs
    for dll in REQUIRED_CUDNN_DLLS:
        if not (cuda_dir / dll).exists():
            return False
    return True


def is_cublas_installed() -> bool:
    """Check if cuBLAS libraries are already installed."""
    if IS_LINUX:
        # On Linux, check nvidia pip packages for libcublas
        return _find_nvidia_pip_lib('libcublas')

    cuda_dir = get_cuda_dir()
    if not cuda_dir.exists():
        return False

    # Check for the required cuBLAS DLLs
    for dll in REQUIRED_CUBLAS_DLLS:
        if not (cuda_dir / dll).exists():
            return False
    return True


def is_cuda_libs_installed() -> bool:
    """Check if all required CUDA libraries (cuDNN + cuBLAS) are installed."""
    return is_cudnn_installed() and is_cublas_installed()


def clear_cuda_dir() -> bool:
    """Clear the local CUDA directory. Returns True if successful."""
    cuda_dir = get_cuda_dir()
    if cuda_dir.exists():
        try:
            shutil.rmtree(cuda_dir)
            log.info("Cleared CUDA directory", path=str(cuda_dir))
            return True
        except Exception as e:
            log.error("Failed to clear CUDA directory", error=str(e))
            return False
    return True


def get_cudnn_path() -> Optional[Path]:
    """Get path to local cuDNN installation if it exists."""
    cuda_dir = get_cuda_dir()
    if is_cudnn_installed():
        return cuda_dir
    return None


def add_cudnn_to_path():
    """Add local cuDNN directory to system PATH."""
    cuda_dir = get_cuda_dir()
    if cuda_dir.exists():
        cuda_str = str(cuda_dir)
        current_path = os.environ.get("PATH", "")
        if cuda_str not in current_path:
            os.environ["PATH"] = cuda_str + os.pathsep + current_path
            log.info("Added cuDNN to PATH", path=cuda_str)


def _download_and_extract(
    url: str,
    name: str,
    cuda_dir: Path,
    ctx,
    cancel_check: Optional[Callable[[], bool]],
    base_downloaded: int,
    total_combined: int,
) -> tuple[bool, Optional[str], int]:
    """
    Download and extract a single archive.

    Returns:
        Tuple of (success, error_message, bytes_downloaded)
    """
    global _download_progress
    import urllib.request
    import urllib.error

    log.info(f"Starting {name} download", url=url)
    _download_progress.status = f"Downloading {name}..."

    tmp_path = cuda_dir / f"{name}_partial.zip"
    
    existing_size = 0
    if tmp_path.exists():
        existing_size = tmp_path.stat().st_size

    headers = {"User-Agent": "Dictore/1.0"}
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"
        log.info(f"Resuming {name} download from {existing_size} bytes")

    try:
        req = urllib.request.Request(url, headers=headers)
        try:
            response = urllib.request.urlopen(req, context=ctx, timeout=60)
            status_code = response.getcode()
        except urllib.error.HTTPError as e:
            if e.code == 416:
                # Requested range not satisfiable - file is probably fully downloaded
                log.info(f"Range not satisfiable for {name}, assuming download complete.")
                response = None
                status_code = 416
            else:
                raise e

        downloaded = existing_size

        if response is not None:
            if status_code == 200:
                # Server ignored Range or we didn't send one
                mode = "wb"
                downloaded = 0
                existing_size = 0
            else:
                # 206 Partial Content
                mode = "ab"

            file_size = int(response.headers.get("Content-Length", 0)) + existing_size
            chunk_size = 1024 * 1024  # 1MB chunks

            log.info(f"Downloading {name}", total_mb=file_size / (1024*1024))

            with open(tmp_path, mode) as f:
                while True:
                    if cancel_check and cancel_check():
                        log.info(f"{name} download cancelled")
                        return False, "Download cancelled", downloaded

                    try:
                        chunk = response.read(chunk_size)
                    except Exception as e:
                        log.error(f"Network error reading chunk for {name}: {e}")
                        return False, f"Network error: {e}", downloaded

                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress tracker (combined progress)
                    _download_progress.downloaded_bytes = base_downloaded + downloaded
                    _download_progress.percent = int(((base_downloaded + downloaded) / total_combined) * 100) if total_combined > 0 else 0

            response.close()

        log.info(f"{name} download complete, extracting DLLs")
        _download_progress.status = f"Extracting {name}..."

        # Extract DLLs
        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for zip_name in zf.namelist():
                    basename = os.path.basename(zip_name)
                    if basename.endswith(".dll"):
                        target = cuda_dir / basename
                        with zf.open(zip_name) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        log.debug("Extracted", dll=basename)
        except zipfile.BadZipFile:
            log.error(f"Bad zip file for {name}, removing partial file")
            try:
                tmp_path.unlink()
            except Exception:
                pass
            return False, "Corrupted download file, please try again", 0

        # Success! Remove the partial zip to save space
        try:
            tmp_path.unlink()
        except Exception:
            pass

        return True, None, downloaded

    except Exception as e:
        error_msg = str(e)
        log.error(f"Error downloading {name}", error=error_msg)
        return False, error_msg, existing_size


def download_cudnn(
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Download and install cuDNN and cuBLAS from NVIDIA CDN.

    Args:
        progress_callback: Called with (downloaded_bytes, total_bytes)
        cancel_check: Called to check if download should be cancelled

    Returns:
        Tuple of (success, error_message)
    """
    global _download_progress
    import urllib.request
    import ssl

    # On Linux, CUDA libs come from pip packages - no download needed
    if IS_LINUX:
        if is_cuda_libs_installed():
            return True, None
        return False, "On Linux, install nvidia-cublas-cu12 pip package for CUDA support."

    # Reset and start progress tracking
    reset_download_progress()
    _download_progress.downloading = True
    _download_progress.status = "Initializing..."

    cuda_dir = get_cuda_dir()
    cuda_dir.mkdir(parents=True, exist_ok=True)

    try:
        ctx = ssl.create_default_context()

        # Get total size of both downloads for accurate progress
        cudnn_size = 0
        cublas_size = 0

        try:
            _download_progress.status = "Checking download sizes..."
            req = urllib.request.Request(CUDNN_URL, method='HEAD', headers={"User-Agent": "Dictore/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
                cudnn_size = int(response.headers.get("Content-Length", 550 * 1024 * 1024))
        except Exception:
            cudnn_size = 550 * 1024 * 1024  # ~550MB estimate

        try:
            req = urllib.request.Request(CUBLAS_URL, method='HEAD', headers={"User-Agent": "Dictore/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
                cublas_size = int(response.headers.get("Content-Length", 330 * 1024 * 1024))
        except Exception:
            cublas_size = 330 * 1024 * 1024  # ~330MB estimate

        total_size = cudnn_size + cublas_size
        _download_progress.total_bytes = total_size

        log.info("Starting CUDA libraries download", cudnn_mb=cudnn_size/(1024*1024), cublas_mb=cublas_size/(1024*1024))

        # Download cuDNN first
        cudnn_downloaded = cudnn_size if is_cudnn_installed() else 0
        if not is_cudnn_installed():
            success, error, cudnn_downloaded = _download_and_extract(
                CUDNN_URL, "cuDNN", cuda_dir, ctx, cancel_check, 0, total_size
            )
            if not success:
                _download_progress.downloading = False
                _download_progress.complete = True
                _download_progress.error = error
                return False, error
        else:
            log.info("cuDNN already installed, skipping download")

        # Download cuBLAS
        if not is_cublas_installed():
            success, error, cublas_downloaded = _download_and_extract(
                CUBLAS_URL, "cuBLAS", cuda_dir, ctx, cancel_check, cudnn_downloaded, total_size
            )
            if not success:
                _download_progress.downloading = False
                _download_progress.complete = True
                _download_progress.error = error
                return False, error
        else:
            log.info("cuBLAS already installed, skipping download")

        log.info("CUDA libraries installation complete", path=str(cuda_dir))
        _download_progress.status = "Verifying installation..."

        # Verify installation
        if is_cuda_libs_installed():
            _download_progress.downloading = False
            _download_progress.complete = True
            _download_progress.success = True
            _download_progress.status = "Complete"
            return True, None
        else:
            missing = []
            if not is_cudnn_installed():
                missing.append("cuDNN")
            if not is_cublas_installed():
                missing.append("cuBLAS")
            error = f"DLLs extracted but verification failed. Missing: {', '.join(missing)}"
            _download_progress.downloading = False
            _download_progress.complete = True
            _download_progress.error = error
            return False, error

    except urllib.error.URLError as e:
        error = f"Network error: {e.reason}"
        log.error("CUDA download failed", error=error)
        _download_progress.downloading = False
        _download_progress.complete = True
        _download_progress.error = error
        return False, error
    except Exception as e:
        error = str(e)
        log.error("CUDA download failed", error=error)
        _download_progress.downloading = False
        _download_progress.complete = True
        _download_progress.error = error
        return False, error


def get_download_size_mb() -> int:
    """Get approximate download size in MB."""
    return 880  # cuDNN ~550MB + cuBLAS ~330MB


def get_download_progress() -> dict:
    """Get current download progress as a dict for RPC."""
    return {
        "downloading": _download_progress.downloading,
        "downloadedBytes": _download_progress.downloaded_bytes,
        "totalBytes": _download_progress.total_bytes,
        "percent": _download_progress.percent,
        "error": _download_progress.error,
        "complete": _download_progress.complete,
        "success": _download_progress.success,
        "status": _download_progress.status,
    }


def reset_download_progress():
    """Reset progress tracker for a new download."""
    global _download_progress
    _download_progress = DownloadProgress()
