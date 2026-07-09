import os

import requests
from PIL import Image
from io import BytesIO
import open_clip
import torch
from env import DEVICE

class Clip:
    def __init__(self):
        print("Loading model...")
        try:
            self.device = DEVICE if torch.cuda.is_available() else "cpu"
            print("clip device:", self.device)
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32",
                pretrained="laion2b_s34b_b79k"
            )
            self.model = self.model.to(self.device)
        except Exception as e:
            print("CLIP ERROR:", e)
            return None
        print("Model loaded")

    def get_post_tensor(self, post):

        embedding = post.get("embedding")

        if isinstance(embedding, torch.Tensor):
            return embedding.unsqueeze(0)

        if embedding is not None:
            return torch.tensor(
                embedding,
                dtype=torch.float32,
                device=self.device
            ).unsqueeze(0)

        url = (
            post.get("preview_url")
            or post.get("sample_url")
            or post.get("file_url")
        )

        print("Calculating embedding:", url)

        response = requests.get(url, timeout=20)
        image = Image.open(BytesIO(response.content)).convert("RGB")

        image = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            imageTensor = self.model.encode_image(image)

        imageTensor = imageTensor / imageTensor.norm(
            dim=-1,
            keepdim=True
        )

        post["embedding"] = imageTensor.squeeze(0).cpu()

        return imageTensor
    
CLIP: Clip = Clip()