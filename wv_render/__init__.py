import soundfile as sf

import pyfftw
import pyfftw.builders

import numpy as np

import skia
import ffmpeg

import argparse


parser = argparse.ArgumentParser()
parser.add_argument('INPUT', type=argparse.FileType('rb'))
parser.add_argument('OUTPUT')
parser.add_argument('--width', type=int, default=1920, help='height of visualization')
parser.add_argument('--height', type=int, default=1080, help='width of visualization')
parser.add_argument('--max-frequency', type=int, default=10000, help='max frequency on display')
parser.add_argument('--stroke-color', type=skia.Color, default=skia.ColorBLACK, help='stroke color')
parser.add_argument('--background-color', type=skia.Color, default=skia.ColorYELLOW, help='background color')
parser.add_argument('--stroke-width', type=float, default=2, help='stroke width of path')
parser.add_argument('--gain', type=float, default=1.5, help='spectral gain (increases peak height)')

args = parser.parse_args()

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
hann = np.hanning(2048)

with sf.SoundFile(args.INPUT) as f:
    # TODO Frame synchronization is a problem (i.e. the rate which blocks are read
    # might not match the desired framerate)
    samples = pyfftw.empty_aligned((2048, f.channels), dtype='float', n=16)
    
    bins = np.empty((1025, f.channels), dtype='float')
    bars = np.empty(1025, dtype='float')

    # Only n/2+1 elements of DFT matter, due to Hermitian symmetry of real-valued data
    fft = pyfftw.builders.rfft(samples, axis=0)
    max_bin = int(2048 / f.samplerate * args.max_frequency) # Max 8000Hz (F = n * Fs/N)

    # TODO What should the first point be?
    points = [skia.Point(0, args.height/2)] + \
             [skia.Point(0, 0) for _ in range(max_bin)]
    
    # TODO Either allow user to customize the FFmpeg options, or get rid of FFmpeg.
    # Ideally, FFmpeg would have been beneficial if we could feed it GL surfaces
    # and use hardware accelarated codecs (VAAPI, CUDA, etc.) that would use these
    # hardware surfaces directly and encode us a video
    process = (
        ffmpeg.input('pipe:', format='rawvideo', pix_fmt='rgb0', s=f'{args.width}x{args.height}',
                     framerate=f.samplerate/1024)
              .output(args.OUTPUT, pix_fmt='yuv420p')
              .overwrite_output()
              .run_async(pipe_stdin=True)
    )

    coeff1 = args.height / (1024 * f.channels) * args.gain
    xstep = args.width / max_bin

    with skia.Surface.MakeRaster(surface_info) as canvas:
        # TODO use the von-Hann window function
        for _ in f.blocks(out=samples, overlap=1024):
            for c in range(f.channels):
                np.multiply(samples[:,c], hann, out=samples[:,c])

            transform = fft(samples)
            
            # This unconventional use is so that temporary copies aren't created,
            # as they are, by virtue, quite expensive
            np.abs(transform, out=bins)
            np.sum(bins, axis=1, out=bars)

            # Reuse the path object
            path.reset()

            # Clear the screen
            canvas.drawColor(args.background_color)

            x = 0
            sign = 1 # This creates a wavy effect (Adobe AE)

            for i, v in enumerate(bars[1:max_bin+1]):
                points[i+1].set(x, args.height/2 - sign * coeff1 * v/2)
                x += xstep
                sign *= -1

            path.addPoly(points, False)
            canvas.drawPath(path, paint)
            canvas.peekPixels(pixmap)

            process.stdin.write(pixmap)
        
        # All has finished now
        process.stdin.close()
        
    # Wait for FFmpeg to finish encoding
    process.wait()
