import io
import os

import mlflow
import numpy as np
import torch
from fastapi import FastAPI, File, UploadFile
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

model = mlflow.pyfunc.load_model("models:/food11@champion")

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    image = Image.open(io.BytesIO(await file.read())).convert("RGB")
    batch = TRANSFORM(image).unsqueeze(0).numpy().astype(np.float32)

    logits = torch.from_numpy(np.asarray(model.predict(batch)))
    probs = torch.softmax(logits, dim=1)[0]
    idx = int(probs.argmax())

    return {"category": CLASS_NAMES[idx], "confidence": float(probs[idx])}
