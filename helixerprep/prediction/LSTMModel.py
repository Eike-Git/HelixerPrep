#! /usr/bin/env python3
import random
import numpy as np
from keras.models import Sequential
from keras.layers import LSTM, CuDNNLSTM, Dense, Bidirectional
from HelixerModel import HelixerModel, HelixerSequence, acc_row, acc_g_row, acc_ig_row


class LSTMSequence(HelixerSequence):
    def __getitem__(self, idx):
        usable_idx_slice = self.usable_idx[idx * self.batch_size:(idx + 1) * self.batch_size]
        X = np.stack(self.x_dset[sorted(list(usable_idx_slice))])  # got to provide a sorted list of idx
        y = np.stack(self.y_dset[sorted(list(usable_idx_slice))])
        sw = np.stack(self.sw_dset[sorted(list(usable_idx_slice))])
        return X, y, sw


class LSTMModel(HelixerModel):

    def __init__(self):
        super().__init__()
        self.parser.add_argument('-u', '--units', type=int, default=4)
        self.parser.add_argument('-l', '--layers', type=int, default=1)
        self.parse_args()

    def sequence_cls(self):
        return LSTMSequence

    def model(self):
        model = Sequential()
        # input layer
        if self.only_cpu:
            model.add(Bidirectional(
                LSTM(self.units, return_sequences=True, input_shape=(None, 4)),
                input_shape=(None, 4)
            ))
        else:
            model.add(Bidirectional(
                CuDNNLSTM(self.units, return_sequences=True, input_shape=(None, 4)),
                input_shape=(None, 4)
            ))

        # potential next layers
        if self.layers > 1:
            for _ in range(self.layers - 1):
                if self.only_cpu:
                    model.add(Bidirectional(LSTM(self.units, return_sequences=True)))
                else:
                    model.add(Bidirectional(CuDNNLSTM(self.units, return_sequences=True)))

        model.add(Dense(3, activation='sigmoid'))
        return model

    def compile_model(self, model):
        if self.one_hot:
        model.compile(optimizer=self.optimizer,
                      loss='binary_crossentropy',
                      sample_weight_mode='temporal',
                      metrics=[
                          'accuracy',
                          acc_row,
                          acc_g_row,
                          acc_ig_row,
                      ])


if __name__ == '__main__':
    model = LSTMModel()
    model.run()
