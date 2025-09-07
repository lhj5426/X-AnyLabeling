import re
import math
import textwrap
import platform
import subprocess
import webbrowser
from difflib import SequenceMatcher
from importlib_metadata import version as get_package_version
from typing import Iterator, Tuple, List, Optional, Dict, Any


def format_bold(text: str) -> str:
    """
    Format text with bold ANSI escape codes for terminal display.

    This function wraps the provided text with ANSI escape sequences to
    display it in bold format when printed to terminals that support
    ANSI color codes.

    Args:
        text (str): The text to format in bold.

    Returns:
        str: Text wrapped with bold ANSI escape codes.

    Examples:
        >>> bold_text = format_bold("Important Message")
        >>> print(bold_text)  # Displays in bold in terminal
        
    Note:
        Only works in terminals that support ANSI escape codes.
        In unsupported terminals, the escape codes may be visible as text.
    """
    return f"\033[1m{text}\033[0m"


def format_color(text, color_code):
    return f"\033[{color_code}m{text}\033[0m"


def gradient_text(
    text: str,
    start_color: Tuple[int, int, int] = (0, 0, 255),
    end_color: Tuple[int, int, int] = (255, 0, 255),
    frequency: float = 1.0,
) -> str:
    def color_function(t: float) -> Tuple[int, int, int]:
        def interpolate(start: float, end: float, t: float) -> float:
            # Use a sine wave for smooth, periodic interpolation
            return (
                start
                + (end - start) * (math.sin(math.pi * t * frequency) + 1) / 2
            )

        return tuple(
            round(interpolate(s, e, t)) for s, e in zip(start_color, end_color)
        )

    def gradient_gen(length: int) -> Iterator[Tuple[int, int, int]]:
        return (color_function(i / (length - 1)) for i in range(length))

    gradient = gradient_gen(len(text))
    return "".join(
        f"\033[38;2;{r};{g};{b}m{char}\033[0m"
        for char, (r, g, b) in zip(text, gradient)
    )  # noqa: E501


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def indent_text(text, indent=4):
    return textwrap.indent(text, " " * indent)


def is_chinese(s="人工智能"):
    # Is string composed of any Chinese characters?
    return bool(re.search("[\u4e00-\u9fff]", str(s)))


def is_possible_rectangle(points: List[List[float]]) -> bool:
    """
    Check if a set of 4 points can form a valid rectangle.

    This function determines whether four points have the geometric properties
    necessary to form a rectangle by comparing the squared distances between
    adjacent vertices. A valid rectangle has two pairs of equal opposite sides.

    Args:
        points (List[List[float]]): List of 4 points, each as [x, y] coordinates
            in the format [[x1, y1], [x2, y2], [x3, y3], [x4, y4]].

    Returns:
        bool: True if the points can form a rectangle, False otherwise.

    Examples:
        >>> # Perfect rectangle
        >>> rect_points = [[0, 0], [1, 0], [1, 1], [0, 1]]
        >>> print(is_possible_rectangle(rect_points))  # True
        
        >>> # Irregular quadrilateral
        >>> irreg_points = [[0, 0], [2, 1], [3, 4], [1, 3]]
        >>> print(is_possible_rectangle(irreg_points))  # False
        
    Note:
        Requires exactly 4 points to be considered a potential rectangle.
        Uses squared distance calculations for efficiency (avoids sqrt).
        Points should be provided in a consistent order (clockwise/counterclockwise).
    """
    if len(points) != 4:
        return False

    # Check if four points form a rectangle
    # The points are expected to be in the format:
    # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    dists = [square_dist(points[i], points[(i + 1) % 4]) for i in range(4)]
    dists.sort()

    # For a rectangle, the two smallest distances
    # should be equal and the two largest should be equal
    return dists[0] == dists[1] and dists[2] == dists[3]


def square_dist(p: List[float], q: List[float]) -> float:
    """
    Calculate the squared Euclidean distance between two points.

    This function computes the squared distance between two 2D points,
    which is more efficient than calculating the actual distance when
    only relative distances are needed for comparison.

    Args:
        p (List[float]): First point as [x, y] coordinates.
        q (List[float]): Second point as [x, y] coordinates.

    Returns:
        float: The squared distance between the two points.

    Examples:
        >>> point1 = [0, 0]
        >>> point2 = [3, 4]
        >>> dist_sq = square_dist(point1, point2)
        >>> print(dist_sq)  # 25.0 (actual distance would be 5.0)
        
    Note:
        Avoids expensive square root calculation for better performance.
        Suitable for distance comparisons where relative ordering matters.
    """
    # Calculate the square distance between two points
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


def collect_system_info():
    os_info = platform.platform()
    cpu_info = platform.processor()
    gpu_info = get_gpu_info()
    cuda_info = get_cuda_version()
    python_info = platform.python_version()
    pyqt5_info = get_installed_package_version("PyQt5")
    onnx_info = get_installed_package_version("onnx")
    ort_info = get_installed_package_version("onnxruntime")
    ort_gpu_info = get_installed_package_version("onnxruntime-gpu")
    opencv_contrib_info = get_installed_package_version(
        "opencv-contrib-python-headless"
    )

    system_info = {
        "Operating System": os_info,
        "CPU": cpu_info,
        "GPU": gpu_info,
        "CUDA": cuda_info,
        "Python Version": python_info,
    }
    pkg_info = {
        "PyQt5 Version": pyqt5_info,
        "ONNX Version": onnx_info,
        "ONNX Runtime Version": ort_info,
        "ONNX Runtime GPU Version": ort_gpu_info,
        "OpenCV Contrib Python Headless Version": opencv_contrib_info,
    }

    return system_info, pkg_info


def find_most_similar_label(text: str, valid_labels: List[str]) -> str:
    """
    Find the most similar label from a list of valid labels using fuzzy matching.

    This function uses sequence matching algorithms to find the label that
    most closely resembles the input text, enabling intelligent label
    suggestions and auto-correction functionality.

    Args:
        text (str): The input text to match against valid labels.
        valid_labels (List[str]): List of valid label strings to search within.

    Returns:
        str: The most similar label from the valid_labels list.

    Examples:
        >>> labels = ["cat", "dog", "bird", "car"]
        >>> result = find_most_similar_label("catt", labels)
        >>> print(result)  # "cat"
        
        >>> result = find_most_similar_label("automobile", labels)
        >>> print(result)  # "car" (if it's the closest match)
        
    Note:
        Uses difflib.SequenceMatcher for similarity calculation.
        Returns the label with the highest similarity ratio.
        If no valid labels provided, returns the first label in the list.
    """
    max_similarity = 0
    most_similar_label = valid_labels[0]

    for label in valid_labels:
        similarity = SequenceMatcher(None, text, label).ratio()
        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_label = label

    return most_similar_label


def get_installed_package_version(package_name):
    try:
        return get_package_version(package_name)
    except Exception:
        return None


def get_cuda_version():
    try:
        nvcc_output = subprocess.check_output(["nvcc", "--version"]).decode(
            "utf-8"
        )
        version_line = next(
            (line for line in nvcc_output.split("\n") if "release" in line),
            None,
        )
        if version_line:
            return version_line.split()[-1]
    except Exception:
        return None


def get_gpu_info():
    try:
        smi_output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            encoding="utf-8",
        )
        return ", ".join(smi_output.strip().split("\n"))
    except Exception:
        return None


def open_url(url: str) -> None:
    """Open URL in browser while suppressing TTY warnings"""
    try:
        if platform.system() == "Linux":
            # Check if running in WSL
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    # Use powershell.exe for WSL
                    subprocess.run(
                        [
                            "powershell.exe",
                            "-Command",
                            f'Start-Process "{url}"',
                        ]
                    )
                else:
                    # For native Linux, use xdg-open
                    subprocess.run(
                        ["xdg-open", url], stderr=subprocess.DEVNULL
                    )
        else:
            webbrowser.open(url)
    except Exception:
        # Fallback to regular webbrowser.open
        webbrowser.open(url)
