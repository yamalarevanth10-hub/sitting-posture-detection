import os
import urllib.request

MODELS = {
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
}

def download_models(target_dir="models"):
    os.makedirs(target_dir, exist_ok=True)
    for name, url in MODELS.items():
        file_path = os.path.join(target_dir, name)
        if not os.path.exists(file_path):
            print(f"Downloading {name}...")
            urllib.request.urlretrieve(url, file_path)
            print(f"Downloaded {name} ({os.path.getsize(file_path) / (1024*1024):.2f} MB)")
        else:
            print(f"Model already exists: {name}")

if __name__ == "__main__":
    download_models()
