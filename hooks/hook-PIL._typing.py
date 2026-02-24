"""
Prevent PyInstaller from pulling numpy via Pillow typing-only hints.

PIL._typing conditionally imports numpy.typing behind TYPE_CHECKING=False.
At runtime this import path is never used, but static analysis may still
bundle the whole numpy stack (~25MB+). Excluding it keeps GIF/PNG runtime
support intact because image plugins are handled by hook-PIL.Image.
"""

excludedimports = ["numpy", "numpy.typing"]
