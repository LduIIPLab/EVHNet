# 基于增强Vision Transformer的哈希食品图像检索 - Pytorch

Enhanced ViT Hash Network (EVHNet) utilizes the Vision Transformer to generate the hash code for image retrieval. 
It is tested under different retrieval frameworks such as GreedyHash, CSQ and DPN.





## How to Run

This code uses the Vision Transformer (ViT) code and pretrained model (https://github.com/jeonsworld/ViT-pytorch) and DeepHash framework (https://github.com/swuxyj/DeepHash-pytorch).

Download the ViT pretrained models from official repository and keep under pretrainedVIT directory:

ViT-B_16: https://storage.googleapis.com/vit_models/imagenet21k/ViT-B_16.npz 

ViT-B_32: https://storage.googleapis.com/vit_models/imagenet21k/ViT-B_32.npz

Download data from http://data.vision.ee.ethz.ch/cvl/food-101.tar.g for Food-101 dataset, if not already present under data directory.

Run 

python GreedyHash.py

python CSQ.py

python DPN.py

Select the backbone such as AlexNet, ResNet, ViT-16 , ViT-32 ,EVHNet32 or EVHNet16 before running.

