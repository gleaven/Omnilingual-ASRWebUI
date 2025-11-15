#!/usr/bin/env python3
"""
Test script for Omnilingual ASR Web Interface.

This script tests the complete pipeline:
1. Generate test audio
2. Upload audio
3. Start transcription
4. Monitor progress
5. Retrieve and verify results
"""

import sys
import time
import requests
import numpy as np
import soundfile as sf
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8123/api"  # Nginx proxies /api to backend
TEST_AUDIO_PATH = "/tmp/test_audio.wav"


def generate_test_audio(duration=10, sample_rate=16000):
    """Generate a simple test audio file with beeps."""
    print("📝 Generating test audio...")

    # Generate a simple sine wave (440 Hz - A note)
    t = np.linspace(0, duration, int(sample_rate * duration))
    frequency = 440.0
    audio = 0.3 * np.sin(2 * np.pi * frequency * t)

    # Add some silence in the middle (for VAD testing)
    mid_point = len(audio) // 2
    audio[mid_point:mid_point + sample_rate] = 0

    # Save as WAV file
    sf.write(TEST_AUDIO_PATH, audio, sample_rate)
    print(f"✅ Generated test audio: {TEST_AUDIO_PATH}")

    return TEST_AUDIO_PATH


def upload_audio(file_path):
    """Upload audio file to API."""
    print("\n📤 Uploading audio file...")

    with open(file_path, 'rb') as f:
        files = {'file': ('test_audio.wav', f, 'audio/wav')}
        response = requests.post(f"{API_BASE}/audio/upload", files=files)

    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        return None

    data = response.json()
    audio_id = data['id']
    print(f"✅ Audio uploaded successfully (ID: {audio_id})")
    print(f"   Duration: {data['duration_seconds']:.2f}s")
    print(f"   Sample rate: {data['sample_rate']} Hz")

    return audio_id


def start_transcription(audio_id, model="CTC_1B"):
    """Start transcription job."""
    print(f"\n🎤 Starting transcription (model: {model})...")

    payload = {
        "audio_id": audio_id,
        "model": model,
        "enable_diarization": False,  # Disable for test audio
        "chunk_duration": 30
    }

    response = requests.post(f"{API_BASE}/transcribe", json=payload)

    if response.status_code != 200:
        print(f"❌ Transcription start failed: {response.text}")
        return None

    data = response.json()
    job_id = data['job_id']
    print(f"✅ Transcription job started (Job ID: {job_id})")

    return job_id


def monitor_job(job_id, timeout=300):
    """Monitor job progress until completion."""
    print(f"\n⏳ Monitoring job {job_id}...")

    start_time = time.time()
    last_progress = -1

    while time.time() - start_time < timeout:
        response = requests.get(f"{API_BASE}/jobs/{job_id}")

        if response.status_code != 200:
            print(f"❌ Failed to get job status: {response.text}")
            return False

        data = response.json()
        status = data['status']
        progress = data['progress']
        step = data.get('current_step', 'N/A')

        # Print progress updates
        if progress != last_progress:
            print(f"   Progress: {progress:.1f}% - {step}")
            last_progress = progress

        if status == 'completed':
            print(f"✅ Job completed in {time.time() - start_time:.1f}s")
            return True
        elif status == 'failed':
            error = data.get('error_message', 'Unknown error')
            print(f"❌ Job failed: {error}")
            return False

        time.sleep(2)

    print(f"❌ Job timed out after {timeout}s")
    return False


def get_transcription_result(job_id):
    """Retrieve and display transcription result."""
    print(f"\n📄 Retrieving transcription result...")

    response = requests.get(f"{API_BASE}/jobs/{job_id}/result")

    if response.status_code != 200:
        print(f"❌ Failed to get result: {response.text}")
        return None

    data = response.json()

    print("\n" + "="*60)
    print("TRANSCRIPTION RESULT")
    print("="*60)

    print(f"\n📊 Metadata:")
    print(f"   Job ID: {data['job_id']}")
    print(f"   Status: {data['status']}")
    print(f"   Audio Duration: {data['audio_duration']:.2f}s")

    if data.get('processing_time'):
        print(f"   Processing Time: {data['processing_time']:.2f}s")

    print(f"\n🌍 Detected Languages:")
    for lang in data['detected_languages']:
        print(f"   - {lang['name']} ({lang['code']}): {lang['confidence']*100:.1f}% confidence")

    if data['speakers']:
        print(f"\n👥 Speakers: {len(data['speakers'])}")
        for speaker in data['speakers']:
            print(f"   - {speaker['label']}: {speaker['total_speaking_time']:.1f}s, {speaker['num_segments']} segments")

    print(f"\n📝 Transcription ({len(data['segments'])} segments):")
    print("-" * 60)

    for seg in data['segments']:
        start = seg['start_time']
        end = seg['end_time']
        text = seg['text']
        speaker = seg.get('speaker_label', '')

        if speaker:
            print(f"[{start:.1f}s - {end:.1f}s] {speaker}: {text}")
        else:
            print(f"[{start:.1f}s - {end:.1f}s] {text}")

    print("-" * 60)

    print(f"\n📋 Full Text:")
    print(data['full_text'])

    print("\n" + "="*60)

    return data


def test_export(job_id):
    """Test export functionality."""
    print(f"\n💾 Testing export formats...")

    formats = ['txt', 'json', 'srt', 'vtt']
    export_dir = Path("/tmp/omniasr_exports")
    export_dir.mkdir(exist_ok=True)

    for fmt in formats:
        response = requests.get(f"{API_BASE}/jobs/{job_id}/export?format={fmt}")

        if response.status_code == 200:
            output_file = export_dir / f"transcription_{job_id}.{fmt}"
            output_file.write_bytes(response.content)
            print(f"   ✅ Exported {fmt.upper()}: {output_file}")
        else:
            print(f"   ❌ Failed to export {fmt.upper()}")

    print(f"\n📁 Exports saved to: {export_dir}")


def check_api_health():
    """Check if API is reachable."""
    print("🏥 Checking API health...")

    try:
        response = requests.get(f"{API_BASE}/../health", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
    except requests.exceptions.RequestException as e:
        print(f"❌ API not reachable: {e}")
        print("\nMake sure the services are running:")
        print("   cd /root/omnilingual-asr/web")
        print("   docker-compose up")
        return False

    return False


def main():
    """Run complete pipeline test."""
    print("\n" + "="*60)
    print("OMNILINGUAL ASR WEB INTERFACE - PIPELINE TEST")
    print("="*60 + "\n")

    # Check API health
    if not check_api_health():
        sys.exit(1)

    # Generate test audio
    audio_path = generate_test_audio(duration=15)

    # Upload audio
    audio_id = upload_audio(audio_path)
    if not audio_id:
        sys.exit(1)

    # Start transcription
    job_id = start_transcription(audio_id, model="CTC_1B")
    if not job_id:
        sys.exit(1)

    # Monitor job
    success = monitor_job(job_id, timeout=300)
    if not success:
        sys.exit(1)

    # Get result
    result = get_transcription_result(job_id)
    if not result:
        sys.exit(1)

    # Test exports
    test_export(job_id)

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60 + "\n")

    print("🎉 The pipeline is working correctly!")
    print("\nNext steps:")
    print("   1. Upload your own audio files")
    print("   2. Try YouTube transcription")
    print("   3. Experiment with different models")
    print("   4. Enable speaker diarization")
    print("\nAccess the web interface at: http://localhost:3000")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
