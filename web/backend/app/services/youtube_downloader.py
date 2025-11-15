"""YouTube audio extraction service."""

import os
import yt_dlp
from pathlib import Path
from typing import Dict, Optional


class YouTubeDownloader:
    """Download and extract audio from YouTube videos."""

    def __init__(self, output_dir: str = None):
        """
        Initialize YouTube downloader.

        Args:
            output_dir: Directory to save downloaded audio
        """
        self.output_dir = Path(output_dir or "/tmp/youtube_downloads")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_audio(
        self,
        url: str,
        output_filename: Optional[str] = None
    ) -> Dict:
        """
        Download audio from YouTube video.

        Args:
            url: YouTube video URL
            output_filename: Custom output filename (without extension)

        Returns:
            Dictionary with download info (file_path, title, duration, etc.)
        """
        # Configure yt-dlp options with better headers to avoid 403 errors
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': str(self.output_dir / (output_filename or '%(id)s.%(ext)s')),
            'quiet': False,  # Show errors
            'no_warnings': False,
            'extract_flat': False,
            # Add headers to avoid 403 Forbidden
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            # Additional options for better compatibility
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                info = ydl.extract_info(url, download=True)

                # Get the downloaded file path
                output_path = ydl.prepare_filename(info)
                # Replace extension with .wav (since we're extracting audio)
                output_path = os.path.splitext(output_path)[0] + '.wav'

                return {
                    'file_path': output_path,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'upload_date': info.get('upload_date', None),
                    'url': url,
                    'video_id': info.get('id', None),
                }

        except Exception as e:
            raise Exception(f"Failed to download YouTube audio: {str(e)}")

    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL.

        Args:
            url: URL to validate

        Returns:
            True if valid YouTube URL
        """
        youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
        return any(domain in url.lower() for domain in youtube_domains)
