import subprocess
import os

# ----------  convert to browser-playable H.264 ----------
def get_available_encoders():
    """Return a list of available FFmpeg encoders."""
    result = subprocess.run(
        ["ffmpeg", "-encoders"],
        capture_output=True,
        text=True
    )
    return result.stdout

def detect_best_h264_encoder():
    """Pick the fastest available H.264 encoder."""
    encoders = get_available_encoders()
    print(encoders)

    priority = [
        "h264_videotoolbox",  # macOS hardware
        "h264_nvenc",         # NVIDIA GPU
        "h264_qsv",           # Intel Quick Sync
        "h264_amf",           # AMD GPU
        "libx264"             # CPU fallback
    ]

    for encoder in priority:
        if encoder in encoders:
            return encoder

    raise RuntimeError("No H.264 encoder found in ffmpeg")

def convert_to_h264(input_path, output_path):
    encoder = detect_best_h264_encoder()
    print(encoder)
    print(f"Using encoder: {encoder}")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", encoder,
        "-b:v", "5M",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]

    subprocess.run(cmd, check=True)
    os.remove(input_path)
    return
