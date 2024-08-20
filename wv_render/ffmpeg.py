import av
import av.video
import av.video.reformatter

from os.path import splitext

class FFmpegOutput:
    def __init__(self, file: str, width: int, height: int, fps: int | float):
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

    def write_pixmap(self, pixmap):
        self.frame.make_writable()
        self.frame.planes[0].update(pixmap)

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