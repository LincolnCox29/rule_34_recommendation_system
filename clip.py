import os

import requests
from PIL import Image
from io import BytesIO
import open_clip
import torch

DEVICE = os.getenv("DEVICE")

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

        url = (
            post.get("preview_url")
            or post.get("sample_url")
            or post.get("file_url")
        )

        print("Geting tensor of: ", url)
        res = requests.get(url)
        image = Image.open(BytesIO(res.content))

        image = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            imageTensor = self.model.encode_image(image)

        return imageTensor / imageTensor.norm(dim=-1, keepdim=True)