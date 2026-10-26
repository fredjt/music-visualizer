"""Test plugin for integration testing."""
from audio_visualizer.visualizers.base import VisualizerPlugin, PluginMetadata


class TestPlugin(VisualizerPlugin):
    """A test plugin that creates a simple colored bar."""

    metadata = PluginMetadata(
        name="test",
        display_name="Test Plugin",
        description="A simple test plugin for integration testing",
        version="1.0.0",
    )

    def build_filter(self, width, height, fps, audio_index=0, video_index=1):
        return (
            f"[{audio_index}:a] aresample={fps}[resampled]; "
            f"[{video_index}:v] format=yuv420p[bg]; "
            f"[bg] split=2[bg1][bg2]; "
            f"[bg1] drawcolor=red:size={width}x{height//2}[top]; "
            f"[bg2] drawcolor=blue:size={width}x{height//2}:y={height//2}[bottom]; "
            f"[top][bottom] vstack[out]"
        )
