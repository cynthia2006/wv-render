# wv-render

**wv-render** stands for *wave render*, although it actually renders a spectral representation of the audio that was submitted. It is not on-par scientific accuracy, and is for creative purposes only.

## Original Idea

Idea for **wv-render** originally begun out as a C program that used Cairo to render submitted audio into a waveform, but it wasn't extended further and left in dark.

## Present
This project ressurects the aforementioned idea, and instead of using C directly, uses Python along with various high performance libraries. Native Python code is kept to a minimum, and most of the mathematical work is done by other libraries.

## Caveats
Only video is exported, audio isn't, so to recombine the audio, you could use FFmpeg. 