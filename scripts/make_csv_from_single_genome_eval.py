#! /usr/bin/env python3
import os
import h5py
import numpy as np
import argparse
from helixerprep.prediction.ConfusionMatrix import ConfusionMatrix

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--server', type=str, default='clc')
parser.add_argument('-nni', '--nni-id', type=str, required=True)
parser.add_argument('-i', '--ignore', action='append')
parser.add_argument('-er', '--error-rates', action='store_true')
args = parser.parse_args()

assert args.server in ['clc', 'cluster']
assert len(args.nni_id) == 8

if args.server == 'clc':
    nni_base = '/mnt/data/experiments_backup/nni_clc_server/nni/experiments/'
else:
    nni_base = '/mnt/data/experiments_backup/nni_cluster/nni/experiments/'
trials_folder = '{}/{}/trials'.format(nni_base, args.nni_id)

header = ['genome', 'acc_overall', 'f1_ig', 'f1_utr', 'f1_exon', 'f1_intron', 'legacy_f1_cds',
          'f1_genic']
if args.error_rates:
    header += ['base_level_error_rate', 'padded_bases_rate', 'sequence_error_rate']
header += ['nni_id']
print(','.join(header))

for folder in os.listdir(trials_folder):
    if args.ignore and folder in args.ignore:
        continue
    # get genome name
    parameters = eval(open('{}/{}/parameter.cfg'.format(trials_folder, folder)).read())
    path = parameters['parameters']['test_data']
    # genome = path.split('/')[5]  # when from cluster
    genome = path.split('/')[6]

    # get sequence error rate
    f = h5py.File('/home/felix/Desktop/data/single_genomes/' + genome + '/h5_data_20k/test_data.h5')
    n_samples = f['/data/X'].shape[0]
    err = np.array(f['/data/err_samples'])
    n_err_samples = np.count_nonzero(err == True)
    sequence_error_rate = n_err_samples / n_samples

    # get base level error rate (including padding) iterativly to avoid running into memory issues
    if args.error_rates:
        sw_dset = f['/data/sample_weights']
        y_dset = f['/data/y']
        step_size = 1000
        n_error_bases = 0
        n_padded_bases = 0
        idxs = np.array_split(np.arange(len(sw_dset)), len(sw_dset) // step_size)
        for slice_idxs in idxs:
            sw_slice = sw_dset[list(slice_idxs)]
            y_slice = y_dset[list(slice_idxs)]
            n_error_bases += np.count_nonzero(sw_slice == 0)
            n_padded_bases += np.count_nonzero(np.all(y_slice == 0, axis=-1))
        base_level_error_rate = n_error_bases / sw_dset.size
        padded_bases_rate = n_padded_bases / sw_dset.size

    # parse metric table
    log_file = open('{}/{}/trial.log'.format(trials_folder, folder))
    f1_scores = []
    for line in log_file:
        if 'Precision' in line:  # table start
            next(log_file)  # skip line
            for i in range(6):
                line = next(log_file)
                f1_scores.append(line.strip().split('|')[4].strip())
                if i == 3:
                    next(log_file)  # skip line
            break  # stop at the last line of the metric table

    # parse total accuracy
    next(log_file)
    line = next(log_file)
    acc_overall = line.strip().split(' ')[-1]

    # merge everything into one string
    str_rows = [genome, acc_overall] + f1_scores
    if args.error_rates:
        error_rates = [base_level_error_rate, padded_bases_rate, sequence_error_rate]
        str_rows += ['{:.4f}'.format(n) for n in error_rates]
    str_rows += [folder]
    print(','.join(str_rows))
