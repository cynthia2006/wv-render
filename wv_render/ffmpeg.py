import av
import av.audio.fifo
import av.video
import av.video.reformatter
import av.audio
import av.audio.resampler

from os.path import splitext

class FFmpegOutput:
    def __init__(self, file, width: int, height: int, fps: int | float):
        _, ext = splitext(file)      
        if ext != '.mkv':
            raise NotImplementedError
        
        container = av.open(file, mode='w')
        
        stream = container.add_stream('h264', rate=fps)
        stream.width = width
        stream.height = height

        self.width = width
        self.height = height
        self.container = container
        self.stream = stream
        self.frame = av.video.frame.VideoFrame(width, height, 'rgb0')
        self.scaler = av.video.reformatter.VideoReformatter()
        self.pts = 0

    def write_pixmap(self, pixmap):
        self.frame.make_writable()
        self.frame.pts = self.pts
        self.frame.planes[0].update(pixmap)

        self.pts += 1

        # We are primarily concerned with the pixel format conversion
        new_frame = self.scaler.reformat(self.frame,
                                         width=self.width,
                                         height=self.height,
                                         format='yuv420p')

        for packet in self.stream.encode(new_frame):
            self.container.mux(packet)

    def flush(self):
        for packet in self.stream.encode():
            self.container.mux(packet)

class FFmpegInput:
    def __init__(self, file, stream: int = 0, length: int = 2048, overlap: int = 1024):
        container = av.open(file)

        self.resampler = av.audio.resampler.AudioResampler(format='flt',
                                                           layout='mono',
                                                           rate=48000,
                                                           frame_size=length)
        self.fifo = av.audio.fifo.AudioFifo()
        self.length = length
        self.overlap = overlap
        self.stream = container.streams.audio[stream]
        self.decoded_stream = container.decode(audio=stream)

    def blocks(self):
        # Total frames read from the FIFO queue (not in total)
        frames_read = 0
        hit_eof = False
        
        while True:
            for frame in self.fifo.read_many(self.length, partial=hit_eof):
                frames_read += 1
                yield frame.to_ndarray()[0]

            if frames_read > 0 and not hit_eof:
                frames_read = 0

                if hit_eof:
                    break
                # continue
            else:
                if hit_eof:
                    break

                try:
                    decoded_frame = next(self.decoded_stream)
                    resampled_frames = self.resampler.resample(decoded_frame)

                    for frame in resampled_frames:
                        frame.pts = None
                        self.fifo.write(frame)
                except StopIteration:
                    hit_eof = True
                

