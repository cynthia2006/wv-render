import pyfftw
import pyfftw.builders

import numpy as np

import skia

import argparse

from os.path import splitext
from .ffmpeg import FFmpegInput, FFmpegOutput

parser = argparse.ArgumentParser()
parser.add_argument('INPUT', type=argparse.FileType('rb'))
parser.add_argument('--width', type=int, default=1920, help='height of visualization')
parser.add_argument('--height', type=int, default=1080, help='width of visualization')
parser.add_argument('--min-frequency', type=int, default=50, help='minimum frequency')
parser.add_argument('--max-frequency', type=int, default=10000, help='max frequency on display')
parser.add_argument('--stroke-color', type=lambda c: skia.Color4f.FromColor(int(c, base=16)), default=skia.ColorBLACK, help='stroke color')
parser.add_argument('--background-color', type=lambda c: skia.Color4f.FromColor(int(c, base=16)), default=skia.ColorYELLOW, help='background color')
parser.add_argument('--stroke-width', type=float, default=2, help='stroke width of path')
parser.add_argument('--gain', type=float, default=2, help='spectral gain (increases peak height)')

args = parser.parse_args()
output_file = splitext(args.INPUT.name)[0] + '.mkv'

# Ideally, we should be using OpenGL accelarated Skia rendering. Although it requires,
# significant amount of biolerplate code. The OpenGL context could be created using
# GLFW, SDL, X11, or EGL (Wayland), etc
surface_info = skia.ImageInfo.Make(args.width, args.height,
                                    skia.ColorType.kRGB_888x_ColorType,
                                    skia.AlphaType.kOpaque_AlphaType)

pixmap = skia.Pixmap()
paint = skia.Paint(
    AntiAlias=True,
    Style=skia.Paint.kStroke_Style,
    StrokeWidth=args.stroke_width,
    Color=args.stroke_color,
)
path = skia.Path()
bg_color = args.background_color
margin = 0.05 * args.width  # 0.05vw

# Hanning window with 50% overlap (optimal)
hann = np.hanning(2048)

ffmpeg_input = FFmpegInput(args.INPUT.name)
ffmpeg_output = FFmpegOutput(output_file, args.width, args.height, fps=48000/2048)

# TODO Frame synchronization is a problem (i.e. the rate which blocks are read
# might not match the desired framerate)
samples = pyfftw.empty_aligned(2048, dtype='float', n=16)
bins = np.empty(1025, dtype='float')

fft = pyfftw.builders.rfft(samples, axis=0)
bin_width = 2048 / 48000

min_bin = int(bin_width * args.min_frequency)
max_bin = int(bin_width * args.max_frequency) # (F = n * Fs/N)

# TODO What should the first point be?
points = [skia.Point(0, 0) for _ in range(max_bin - min_bin)]

height = args.height
coeff1 = height / 1024 * args.gain
xstep = (args.width - 2 * margin) / (max_bin - min_bin)

print(len(points), min_bin, max_bin, bin_width)

surface = skia.Surface.MakeRaster(surface_info)

with surface as canvas:
    for block in ffmpeg_input.blocks():
        samples[:] = block

        # TODO Add overlapping (PyAV won't allow us to!)
        np.multiply(samples, hann, out=samples)

        transform = fft(samples)

        np.abs(transform, out=bins)

        canvas.drawColor(bg_color)
        path.reset()

        x = margin
        i = 1
        sign = 1 # This creates a wavy effect (Adobe AE)

        # Skip the DC coefficient, which is just the average of all bin values.
        for i, v in enumerate(bins[min_bin:max_bin]):
            points[i].set(x, height/2 - sign * coeff1 * v/2)
            x += xstep
            sign *= -1

        path.addPoly(points, False)

        canvas.drawPath(path, paint)
        canvas.peekPixels(pixmap)

        ffmpeg_output.write_pixmap(pixmap)
    
# Cleanup
ffmpeg_output.flush()
