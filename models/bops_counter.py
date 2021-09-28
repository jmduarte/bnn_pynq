import numpy as np
import torch
import brevitas.nn as qnn
import math

def countNonZeroWeights(model):
    print("In countNonZeroWeights")
    nonzero = total = 0
    layer_count_alive = {}
    layer_count_total = {}
    layer_names = [layer.name for layer in model.layers]
    for name in layer_names:
        module = model.get_layer(name)
        if isinstance(module, torch.nn.Linear) or isinstance(module, qnn.QuantLinear) or isinstance(module, torch.nn.Conv2d) or isinstance(module, qnn.QuantConv2d):
            p_list = module.get_weights()
            for idx, p in enumerate(p_list):
                if idx == 0:
                    curr_name = name + ".weight"
                elif idx == 1:
                    curr_name = name + ".bias"
                tensor = p.data.cpu().numpy()
                nz_count = np.count_nonzero(tensor)
                total_params = np.prod(tensor.shape)
                layer_count_alive.update({name: nz_count})
                layer_count_total.update({name: total_params})
                nonzero += nz_count
                total += total_params
                print(f'{name:20} | nonzeros = {nz_count:7} / {total_params:7} ({100 * nz_count / total_params:6.2f}%) | total_pruned = {total_params - nz_count :7} | shape = {tensor.shape}')
    #for name, p in model.named_parameters():
        #tensor = p.data.cpu().numpy()
        #nz_count = np.count_nonzero(tensor)
        #total_params = np.prod(tensor.shape)
        #layer_count_alive.update({name: nz_count})
        #layer_count_total.update({name: total_params})
        #nonzero += nz_count
        #total += total_params
        #print(f'{name:20} | nonzeros = {nz_count:7} / {total_params:7} ({100 * nz_count / total_params:6.2f}%) | total_pruned = {total_params - nz_count :7} | shape = {tensor.shape}')
    print(f'alive: {nonzero}, pruned : {total - nonzero}, total: {total}, Compression rate : {total/nonzero:10.2f}x  ({100 * (total-nonzero) / total:6.2f}% pruned)')
    print(layer_count_total)
    return nonzero, total, layer_count_alive, layer_count_total

def calc_BOPS(model, input_data_precision=32):
    print("calc_BOPS")
    last_bit_width = input_data_precision
    alive, total, l_alive, l_total = countNonZeroWeights(model)
    b_w = model.weight_precision if hasattr(model, 'weight_precision') else 32
    total_BOPS = 0
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear) or isinstance(module, qnn.QuantLinear) or isinstance(module, torch.nn.Conv2d) or isinstance(module, qnn.QuantConv2d):
            b_a = last_bit_width
            #b_w = module.quant_weight_bit_width #Dont think this is a property I can access sadly, going with precision as given set in model
            if isinstance(module, qnn.QuantConv2d):
                n = module.in_channels
                m = module.out_channels
            else:
                n = module.in_features
                m = module.out_features
            if isinstance(module, torch.nn.Conv2d) or isinstance(module, qnn.QuantConv2d):
                k = module.kernel_size
            else:
                k = 1
            total = l_total[name+'.weight'] + l_total[name+'.bias']
            alive = l_alive[name + '.weight'] + l_alive[name + '.bias']
            p = 1 - ((total - alive) / total)  # fraction of layer remaining
            #assuming b_a is the output bitwidth of the last layer
            #module_BOPS = m*n*p*(b_a*b_w + b_a + b_w + math.log2(n))
            module_BOPS = m * n * k * k * (p * b_a * b_w + b_a + b_w + math.log2(n*k*k))
            print("{} BOPS: {} = {}*{}*{}({}*{}*{} + {} + {} + {})".format(name, module_BOPS, m, n, k*k, p, b_a, b_w, b_a, b_w, math.log2(n*k*k)))
            last_bit_width = b_w
            total_BOPS += module_BOPS
    scientific_notation = "{:.2e}".format(total_BOPS)
    print("Total BOPS: {} = {}".format(total_BOPS, scientific_notation))
    
    return total_BOPS
