# VTS (DPN with ViT Backbone - ICME 2022)
# paper [Vision Transformer Hashing for Image Retrieval, ICME 2022](https://arxiv.org/pdf/2109.12564.pdf)
# DPN basecode considered from https://github.com/swuxyj/DeepHash-pytorch

from utils.tools import *
from network import *
import os
import torch
import torch.optim as optim
import time
import numpy as np
import random
from TransformerModel.model import VisionTransformer, VIT_CONFIGS
torch.multiprocessing.set_sharing_strategy('file_system')

def get_config():
    config = {
        "dataset": "Food-101",
        
        #"net": AlexNet, "net_print": "AlexNet",
        #"net":ResNet, "net_print": "ResNet",
        "net": VisionTransformer, "net_print": "EVHNet_32", "model_type": "EVHNet_32", "pretrained_dir": "pretrainedVIT/ViT-B_32.npz",
        #"net": VisionTransformer, "net_print": "EVHNet_16", "model_type": "EVHNet_16", "pretrained_dir": "pretrainedVIT/ViT-B_16.npz",
        
        "bit_list": [16, 32, 64],
        "optimizer": {"type": optim.Adam, "optim_params": {"lr": 1e-5}},
        "device": torch.device("cuda"), "save_path": "Checkpoints_Results",
        "epoch": 150, "test_map": 30, "batch_size": 32, "resize_size": 256, "crop_size": 224,
        "info": "DPN", "m": 1, "p": 0.5,
    }
    config = config_dataset(config)
    return config


def train_val(config, bit):
    start_epoch = 1
    Best_mAP = 0
    device = config["device"]
    train_loader, test_loader, dataset_loader, num_train, num_test, num_dataset = get_data(config)
    config["num_train"] = num_train
    
    num_classes = config["n_class"]
    hash_bit = bit
    
    if "ViT" in config["net_print"]:
        vit_config = VIT_CONFIGS[config["model_type"]]
        net = config["net"](vit_config, config["crop_size"], zero_head=True, num_classes=num_classes, hash_bit=hash_bit).to(device)
    else:
        net = config["net"](bit).to(device)
    
    if not os.path.exists(config["save_path"]):
        os.makedirs(config["save_path"])
    best_path = os.path.join(config["save_path"], config["dataset"] + "_" + config["info"] + "_" + config["net_print"] + "_Bit" + str(bit) + "-BestModel.pt")
    trained_path = os.path.join(config["save_path"], config["dataset"] + "_" + config["info"] + "_" + config["net_print"] + "_Bit" + str(bit) + "-IntermediateModel.pt")
    results_path = os.path.join(config["save_path"], config["dataset"] + "_" + config["info"] + "_" + config["net_print"] + "_Bit" + str(bit) + ".txt")
    f = open(results_path, 'a')
    
    if os.path.exists(trained_path):
        print('==> Resuming from checkpoint..')
        checkpoint = torch.load(trained_path)
        net.load_state_dict(checkpoint['net'])
        Best_mAP = checkpoint['Best_mAP']
        start_epoch = checkpoint['epoch'] + 1
    else:
        if "ViT" in config["net_print"]:
            print('==> Loading from pretrained model..')
            net.load_from(np.load(config["pretrained_dir"]))
    
    optimizer = config["optimizer"]["type"](net.parameters(), **(config["optimizer"]["optim_params"]))
    criterion = DPNLoss(config, bit)

    for epoch in range(start_epoch, config["epoch"]+1):
        current_time = time.strftime('%H:%M:%S', time.localtime(time.time()))
        print("%s-%s[%2d/%2d][%s] bit:%d, dataset:%s, training...." % (
            config["info"], config["net_print"], epoch, config["epoch"], current_time, bit, config["dataset"]), end="")
        net.train()
        train_loss = 0
        for image, label, ind in train_loader:
            image = image.to(device)
            label = label.to(device)
            optimizer.zero_grad()
            u = net(image)
            loss = criterion(u, label.float(), ind, config)
            train_loss += loss.item()
            loss.backward()
            optimizer.step()
        train_loss = train_loss / len(train_loader)

        print("\b\b\b\b\b\b\b loss:%.3f" % (train_loss))
        f.write('Train | Epoch: %d | Loss: %.3f\n' % (epoch, train_loss))

        if (epoch) % config["test_map"] == 0:
            # print("calculating test binary code......")
            tst_binary, tst_label = compute_result(test_loader, net, device=device)

            # print("calculating dataset binary code.......")\
            trn_binary, trn_label = compute_result(dataset_loader, net, device=device)

            # print("calculating map.......")
            mAP = CalcTopMap(trn_binary.numpy(), tst_binary.numpy(), trn_label.numpy(), tst_label.numpy(),
                             config["topK"])
            
            if mAP > Best_mAP:
                Best_mAP = mAP
                P, R = pr_curve(trn_binary.numpy(), tst_binary.numpy(), trn_label.numpy(), tst_label.numpy())
                print(f'Precision Recall Curve data:\n"DPN":[{P},{R}],')
                f.write('PR | Epoch %d | ' % (epoch))
                for PR in range(len(P)):
                    f.write('%.5f %.5f ' % (P[PR], R[PR]))
                f.write('\n')
            
                print("Saving in ", config["save_path"])
                state = {
                    'net': net.state_dict(),
                    'Best_mAP': Best_mAP,
                    'epoch': epoch,
                }
                torch.save(state, best_path)
            print("%s epoch:%d, bit:%d, dataset:%s, MAP:%.3f, Best MAP: %.3f" % (
                config["info"], epoch, bit, config["dataset"], mAP, Best_mAP))
            f.write('Test | Epoch %d | MAP: %.3f | Best MAP: %.3f\n'
                % (epoch, mAP, Best_mAP))
            print(config)

            state = {
            	'net': net.state_dict(),
            	'Best_mAP': Best_mAP,
            	'epoch': epoch,
            }
            torch.save(state, trained_path)
        
        '''state = {
            'net': net.state_dict(),
            'Best_mAP': Best_mAP,
            'epoch': epoch,
        }
        torch.save(state, trained_path)'''
    f.close()

class DPNLoss(torch.nn.Module):
    def __init__(self, config, bit):
        super(DPNLoss, self).__init__()
        self.is_single_label = config["dataset"] not in {"nuswide_21",  "coco"}
        self.target_vectors = self.get_target_vectors(config["n_class"], bit, config["p"]).to(config["device"])
        self.multi_label_random_center = torch.randint(2, (bit,)).float().to(config["device"])
        self.m = config["m"]
        self.U = torch.zeros(config["num_train"], bit).float().to(config["device"])
        self.Y = torch.zeros(config["num_train"], config["n_class"]).float().to(config["device"])

    def forward(self, u, y, ind, config):
        self.U[ind, :] = u.data
        self.Y[ind, :] = y.float()

        if "-T" in config["info"]:
            # Ternary Assignment
            u = (u.abs() > self.m).float() * u.sign()

        t = self.label2center(y)
        polarization_loss = (self.m - u * t).clamp(0).mean()

        return polarization_loss

    def label2center(self, y):
        if self.is_single_label:
            hash_center = self.target_vectors[y.argmax(axis=1)]
        else:
            # for multi label, use the same strategy as CSQ
            center_sum = y @ self.target_vectors
            random_center = self.multi_label_random_center.repeat(center_sum.shape[0], 1)
            center_sum[center_sum == 0] = random_center[center_sum == 0]
            hash_center = 2 * (center_sum > 0).float() - 1
        return hash_center

    # Random Assignments of Target Vectors
    def get_target_vectors(self, n_class, bit, p=0.5):
        target_vectors = torch.zeros(n_class, bit)
        for k in range(20):
            for index in range(n_class):
                ones = torch.ones(bit)
                sa = random.sample(list(range(bit)), int(bit * p))
                ones[sa] = -1
                target_vectors[index] = ones
        return target_vectors

    # Adaptive Updating
    def update_target_vectors(self):
        self.U = (self.U.abs() > self.m).float() * self.U.sign()
        self.target_vectors = (self.Y.t() @ self.U).sign()


if __name__ == "__main__":
    config = get_config()
    print(config)
    for bit in config["bit_list"]:
        train_val(config, bit)
