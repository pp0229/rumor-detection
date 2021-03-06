import sys,os
sys.path.append(os.getcwd())
import numpy as np
from torch_geometric.data import DataLoader
from tqdm import tqdm
from torch_geometric.nn import GCNConv,GATConv
import copy
import random
import torch.nn as nn
import torch
import torch.nn.functional as F
from torch_geometric.utils import negative_sampling, add_self_loops
from torch_scatter import scatter_mean

from Process.process import *
from tools.earlystopping import EarlyStopping
from Process.rand5fold import *
from tools.evaluate import *

if sys.argv[2]=='GAE':
  from GAE import Net
elif sys.argv[2]=='VGAE':
  from VGAE import Net
elif sys.argv[2]=='GCN':
  from only_gcn import Net
elif sys.argv[2]=='MVAE':
  from MVAE import Net

# define train epoch
def train_model(treeDic, x_test, x_train,lr, weight_decay,patience,n_epochs,batchsize,dataname,modelname,iter):
    model = Net(5000,64,64).to(device)
    optimizer = torch.optim.Adam(model.parameters(),lr=lr, weight_decay=weight_decay)
    model.train()
    train_losses = []
    val_losses = []
    train_accs = []
    val_accs = []
    score = float('inf')
    early_stopping = EarlyStopping(patience=patience, verbose=True)
    for epoch in range(n_epochs):
        traindata_list, testdata_list = loadData(dataname, treeDic, x_train, x_test, TDdroprate)
        train_loader = DataLoader(traindata_list, batch_size=batchsize, shuffle=False, num_workers=5)
        test_loader = DataLoader(testdata_list, batch_size=batchsize, shuffle=False, num_workers=5)
        avg_loss = []
        avg_acc = []
        batch_idx = 0
        tqdm_train_loader = tqdm(train_loader)
        for Batch_data in tqdm_train_loader:
            Batch_data.to(device)
            logits= model(Batch_data)
            if modelname in ['GAE','VGAE']:
                loss=F.nll_loss(logits,Batch_data.y) + model.loss()
            elif modelname == 'GCN':
                loss=F.nll_loss(logits,Batch_data.y)
            optimizer.zero_grad()
            loss.backward()
            avg_loss.append(loss.item())
            optimizer.step()
            _, pred = logits.max(dim=-1)
            correct = pred.eq(Batch_data.y).sum().item()
            train_acc = correct / len(Batch_data.y)
            avg_acc.append(train_acc)
            print("Iter {:03d} | Epoch {:05d} | Batch{:02d} | Train_Loss {:.4f}| Train_Accuracy {:.4f}".format(iter,epoch, batch_idx,
                                                                                                 loss.item(),
                                                                                                 train_acc))
            batch_idx = batch_idx + 1

        train_losses.append(np.mean(avg_loss))
        train_accs.append(np.mean(avg_acc))

        temp_val_losses = []
        temp_val_accs = []
        temp_val_Acc_all, temp_val_Acc1, temp_val_Prec1, temp_val_Recll1, temp_val_F1, \
        temp_val_Acc2, temp_val_Prec2, temp_val_Recll2, temp_val_F2, \
        temp_val_Acc3, temp_val_Prec3, temp_val_Recll3, temp_val_F3, \
        temp_val_Acc4, temp_val_Prec4, temp_val_Recll4, temp_val_F4 = [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []
        # eval 
        model.eval()
        tqdm_test_loader = tqdm(test_loader)
        for Batch_data in tqdm_test_loader:
            Batch_data.to(device)
            val_out = model(Batch_data)
            if modelname in ['GAE','VGAE']:
                val_loss  = F.nll_loss(val_out, Batch_data.y)+ model.loss()
            elif modelname == 'GCN':
                val_loss  = F.nll_loss(val_out, Batch_data.y)
            temp_val_losses.append(val_loss.item())
            _, val_pred = val_out.max(dim=1)
            correct = val_pred.eq(Batch_data.y).sum().item()
            val_acc = correct / len(Batch_data.y)
            Acc_all, Acc1, Prec1, Recll1, F1, Acc2, Prec2, Recll2, F2, Acc3, Prec3, Recll3, F3, Acc4, Prec4, Recll4, F4 = evaluation4class(
                val_pred, Batch_data.y)
            temp_val_Acc_all.append(Acc_all), temp_val_Acc1.append(Acc1), temp_val_Prec1.append(
                Prec1), temp_val_Recll1.append(Recll1), temp_val_F1.append(F1), \
            temp_val_Acc2.append(Acc2), temp_val_Prec2.append(Prec2), temp_val_Recll2.append(
                Recll2), temp_val_F2.append(F2), \
            temp_val_Acc3.append(Acc3), temp_val_Prec3.append(Prec3), temp_val_Recll3.append(
                Recll3), temp_val_F3.append(F3), \
            temp_val_Acc4.append(Acc4), temp_val_Prec4.append(Prec4), temp_val_Recll4.append(
                Recll4), temp_val_F4.append(F4)
            temp_val_accs.append(val_acc)
        val_losses.append(np.mean(temp_val_losses))
        val_accs.append(np.mean(temp_val_accs))
        print("Epoch {:05d} | Val_Loss {:.4f}| Val_Accuracy {:.4f}".format(epoch, np.mean(temp_val_losses),
                                                                           np.mean(temp_val_accs)))

        res = ['acc:{:.4f}'.format(np.mean(temp_val_Acc_all)),
               'C1:{:.4f},{:.4f},{:.4f},{:.4f}'.format(np.mean(temp_val_Acc1), np.mean(temp_val_Prec1),
                                                       np.mean(temp_val_Recll1), np.mean(temp_val_F1)),
               'C2:{:.4f},{:.4f},{:.4f},{:.4f}'.format(np.mean(temp_val_Acc2), np.mean(temp_val_Prec2),
                                                       np.mean(temp_val_Recll2), np.mean(temp_val_F2)),
               'C3:{:.4f},{:.4f},{:.4f},{:.4f}'.format(np.mean(temp_val_Acc3), np.mean(temp_val_Prec3),
                                                       np.mean(temp_val_Recll3), np.mean(temp_val_F3)),
               'C4:{:.4f},{:.4f},{:.4f},{:.4f}'.format(np.mean(temp_val_Acc4), np.mean(temp_val_Prec4),
                                                       np.mean(temp_val_Recll4), np.mean(temp_val_F4))]
        print('results:', res)
        early_stopping(np.mean(temp_val_losses), np.mean(temp_val_accs), np.mean(temp_val_F1), np.mean(temp_val_F2),
                       np.mean(temp_val_F3), np.mean(temp_val_F4), model, modelname, dataname)
        if np.mean(temp_val_losses) < score:
            score = np.mean(temp_val_losses)
            accs = np.mean(temp_val_accs)
            F1=np.mean(temp_val_F1)
            F2=np.mean(temp_val_F2)
            F3=np.mean(temp_val_F3)
            F4=np.mean(temp_val_F4)

        if early_stopping.early_stop:
            print("Early stopping")
            accs=early_stopping.accs
            F1=early_stopping.F1
            F2 = early_stopping.F2
            F3 = early_stopping.F3
            F4 = early_stopping.F4
            break
    print('*****************************')
    print('Acc {:.4f} | N {:.4f} | F {:.4f} | T {:.4f} | U{:.4f} '.format(accs,F1,F2,F3,F4))
    return train_losses , val_losses ,train_accs, val_accs,accs,F1,F2,F3,F4

lr=0.0005
weight_decay=1e-4
patience=10
n_epochs=40
batchsize=128
datasetname=sys.argv[1] #"Twitter15"、"Twitter16"
modelname = sys.argv[2] # GAE VGAE GCN
iterations=int(1)
model="GCN"
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
test_accs = []
NR_F1 = []
FR_F1 = []
TR_F1 = []
UR_F1 = []
for iter in range(iterations):
    fold0_x_test, fold0_x_train, \
    fold1_x_test,  fold1_x_train,  \
    fold2_x_test, fold2_x_train, \
    fold3_x_test, fold3_x_train, \
    fold4_x_test,fold4_x_train = load5foldData(datasetname)
    treeDic=loadTree(datasetname)
    train_losses, val_losses, train_accs, val_accs0, accs0, F1_0, F2_0, F3_0, F4_0 = train_model(treeDic,
                                                                                               fold0_x_test,
                                                                                               fold0_x_train,
                                                                                               lr, weight_decay,
                                                                                               patience,
                                                                                               n_epochs,
                                                                                               batchsize,
                                                                                               datasetname,modelname,
                                                                                               iter)
    train_losses, val_losses, train_accs, val_accs1, accs1, F1_1, F2_1, F3_1, F4_1 = train_model(treeDic,
                                                                                               fold1_x_test,
                                                                                               fold1_x_train,lr,
                                                                                               weight_decay,
                                                                                               patience,
                                                                                               n_epochs,
                                                                                               batchsize,
                                                                                               datasetname,modelname,
                                                                                               iter)
    train_losses, val_losses, train_accs, val_accs2, accs2, F1_2, F2_2, F3_2, F4_2 = train_model(treeDic,
                                                                                               fold2_x_test,
                                                                                               fold2_x_train,lr,
                                                                                               weight_decay,
                                                                                               patience,
                                                                                               n_epochs,
                                                                                               batchsize,
                                                                                               datasetname,modelname,
                                                                                               iter)
    train_losses, val_losses, train_accs, val_accs3, accs3, F1_3, F2_3, F3_3, F4_3 = train_model(treeDic,
                                                                                               fold3_x_test,
                                                                                               fold3_x_train,lr,
                                                                                               weight_decay,
                                                                                               patience,
                                                                                               n_epochs,
                                                                                               batchsize,
                                                                                               datasetname,modelname,
                                                                                               iter)
    train_losses, val_losses, train_accs, val_accs4, accs4, F1_4, F2_4, F3_4, F4_4 = train_model(treeDic,
                                                                                               fold4_x_test,
                                                                                               fold4_x_train,lr,
                                                                                               weight_decay,
                                                                                               patience,
                                                                                               n_epochs,
                                                                                               batchsize,
                                                                                               datasetname,modelname,
                                                                                               iter)
    test_accs.append((accs0+accs1+accs2+accs3+accs4)/5)
    NR_F1.append((F1_0+F1_1+F1_2+F1_3+F1_4)/5)
    FR_F1.append((F2_0 + F2_1 + F2_2 + F2_3 + F2_4) / 5)
    TR_F1.append((F3_0 + F3_1 + F3_2 + F3_3 + F3_4) / 5)
    UR_F1.append((F4_0 + F4_1 + F4_2 + F4_3 + F4_4) / 5)
print("Total_Test_Accuracy: {:.4f}|NR F1: {:.4f}|FR F1: {:.4f}|TR F1: {:.4f}|UR F1: {:.4f}".format(
    sum(test_accs) / iterations, sum(NR_F1) /iterations, sum(FR_F1) /iterations, sum(TR_F1) / iterations, sum(UR_F1) / iterations))


