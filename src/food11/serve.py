import io
import os
from contextlib import asynccontextmanager
from typing import Annotated

import mlflow
import numpy as np
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image
from torchvision import transforms

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

CLASS_NAMES = [
    "Bread",
    "Dairy product",
    "Dessert",
    "Egg",
    "Fried food",
    "Meat",
    "Noodles-Pasta",
    "Rice",
    "Seafood",
    "Soup",
    "Vegetable-Fruit",
]

TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Module-level so tests can swap in a fake with monkeypatch.setattr(serve, "model", ...)
model = None


def load_model():
    global model
    if os.environ.get("SKIP_MODEL"):
        return
    model = mlflow.pyfunc.load_model("models:/food11@champion")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.post("/predict")
async def predict(file: Annotated[UploadFile, File()]):
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")

    image = Image.open(io.BytesIO(await file.read())).convert("RGB")
    batch = TRANSFORM(image).unsqueeze(0).numpy().astype(np.float32)

    logits = torch.from_numpy(np.asarray(model.predict(batch), dtype=np.float32))
    probs = torch.softmax(logits, dim=1)[0]
    idx = int(probs.argmax())

    return {"category": CLASS_NAMES[idx], "confidence": float(probs[idx])}
