r"""Plant disease prediction using local PlantVillage image prototypes.

The old saved_model/model.keras file in this project is damaged, so loading it
produces random or failed predictions. This predictor builds a stable classifier
from the local C:\pv\data PlantVillage folders instead: it embeds a sample of
images from each supported class with MobileNetV2 and compares new uploads with
those class prototypes.
"""

import io
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image

import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

from disease_db import CLASS_LABELS as FALLBACK_CLASS_LABELS


DATA_DIR = Path(os.environ.get("LEAFSCAN_DATA_DIR", r"C:\pv\data"))
SKIP_FOLDERS = {
    "Background_without_leaves",
    "Plant_leave_diseases_dataset_without_augmentation",
}
CACHE_PATH = Path(__file__).resolve().parent / "saved_model" / "prototype_cache.npz"
IMG_SIZE = (224, 224)
SAMPLE_PER_CLASS = int(os.environ.get("LEAFSCAN_SAMPLE_PER_CLASS", "80"))
BATCH_SIZE = int(os.environ.get("LEAFSCAN_BATCH_SIZE", "32"))
TEMPERATURE = float(os.environ.get("LEAFSCAN_SIM_TEMPERATURE", "18"))
MIN_SUPPORTED_SIMILARITY = float(os.environ.get("LEAFSCAN_MIN_SIMILARITY", "0.38"))


def _dataset_labels():
    if DATA_DIR.is_dir():
        labels = sorted(
            p.name
            for p in DATA_DIR.iterdir()
            if p.is_dir() and p.name not in SKIP_FOLDERS
        )
        if labels:
            return labels
    return list(FALLBACK_CLASS_LABELS)


CLASS_LABELS = _dataset_labels()


def _normalize(vectors):
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.maximum(norms, 1e-8)


def _image_tensor(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(IMG_SIZE)
    arr = np.asarray(img, dtype=np.float32)
    return preprocess_input(arr)


def _file_tensor(path):
    with Image.open(path) as img:
        img = img.convert("RGB").resize(IMG_SIZE)
        arr = np.asarray(img, dtype=np.float32)
    return preprocess_input(arr)


class PlantDiseasePredictor:
    def __init__(self):
        print("[LeafScan] Starting prototype classifier")
        self.backend = "MobileNetV2 prototype matcher"
        self.labels = CLASS_LABELS
        self.model = MobileNetV2(
            input_shape=(*IMG_SIZE, 3),
            include_top=False,
            pooling="avg",
            weights="imagenet",
        )
        self.model.trainable = False
        self.centroids, self.sample_counts = self._load_or_build_prototypes()
        print(f"[LeafScan] Model ready with {len(self.labels)} supported classes")

    def _load_or_build_prototypes(self):
        if CACHE_PATH.is_file():
            try:
                cached = np.load(CACHE_PATH, allow_pickle=False)
                labels = cached["labels"].astype(str).tolist()
                centroids = cached["centroids"].astype(np.float32)
                counts = cached["counts"].astype(np.int32)
                if labels == self.labels and centroids.shape[0] == len(self.labels):
                    print(f"[LeafScan] Loaded prototype cache: {CACHE_PATH}")
                    return _normalize(centroids), counts
            except Exception as exc:
                print(f"[LeafScan] Ignoring invalid prototype cache: {exc}")

        if not DATA_DIR.is_dir():
            raise RuntimeError(
                f"PlantVillage dataset not found at {DATA_DIR}. "
                "Set LEAFSCAN_DATA_DIR to the dataset folder."
            )

        print("[LeafScan] Building prototype cache from local dataset")
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        rng = random.Random(42)
        centroids = []
        counts = []

        for label in self.labels:
            class_dir = DATA_DIR / label
            files = [
                p for p in class_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ]
            if not files:
                raise RuntimeError(f"No images found for supported class {label}")

            files = sorted(files)
            if len(files) > SAMPLE_PER_CLASS:
                files = sorted(rng.sample(files, SAMPLE_PER_CLASS))

            features = []
            for start in range(0, len(files), BATCH_SIZE):
                batch_paths = files[start:start + BATCH_SIZE]
                batch = []
                for path in batch_paths:
                    try:
                        batch.append(_file_tensor(path))
                    except Exception as exc:
                        print(f"[LeafScan] Skipping unreadable image {path}: {exc}")
                if not batch:
                    continue
                batch_features = self.model.predict(np.stack(batch), verbose=0)
                features.append(_normalize(batch_features.astype(np.float32)))

            if not features:
                raise RuntimeError(f"Could not build prototype for {label}")

            class_features = np.concatenate(features, axis=0)
            centroid = _normalize(class_features.mean(axis=0, keepdims=True))[0]
            centroids.append(centroid)
            counts.append(class_features.shape[0])
            print(f"[LeafScan] Prototype {label}: {class_features.shape[0]} images")

        centroids = np.asarray(centroids, dtype=np.float32)
        counts = np.asarray(counts, dtype=np.int32)
        np.savez_compressed(
            CACHE_PATH,
            labels=np.asarray(self.labels),
            centroids=centroids,
            counts=counts,
        )
        print(f"[LeafScan] Saved prototype cache: {CACHE_PATH}")
        return centroids, counts

    def predict(self, image_bytes: bytes, top_k: int = 5) -> list[dict]:
        tensor = np.expand_dims(_image_tensor(image_bytes), axis=0)
        feature = self.model.predict(tensor, verbose=0).astype(np.float32)
        feature = _normalize(feature)[0]

        similarities = self.centroids @ feature
        scaled = similarities * TEMPERATURE
        exp = np.exp(scaled - scaled.max())
        probs = exp / exp.sum()

        top_indices = np.argsort(probs)[::-1][:top_k]
        top_similarity = float(similarities[top_indices[0]])
        supported = top_similarity >= MIN_SUPPORTED_SIMILARITY

        return [
            {
                "class": self.labels[i],
                "probability": float(probs[i]),
                "similarity": float(similarities[i]),
                "supported": supported,
            }
            for i in top_indices
        ]
