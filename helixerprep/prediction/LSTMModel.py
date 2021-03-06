#! /usr/bin/env python3
import random
import numpy as np

from keras_layer_normalization import LayerNormalization
from keras.models import Sequential
from keras.layers import LSTM, CuDNNLSTM, Dense, Bidirectional, Activation, Reshape
from HelixerModel import HelixerModel, HelixerSequence


class LSTMSequence(HelixerSequence):
    def __init__(self, model, h5_file, mode, shuffle):
        super().__init__(model, h5_file, mode, shuffle)
        if self.class_weights is not None:
            assert not mode == 'test'  # only use class weights during training and validation

    def __getitem__(self, idx):
        pool_size = self.model.pool_size
        usable_idx_slice = self.usable_idx[idx * self.batch_size:(idx + 1) * self.batch_size]
        usable_idx_slice = sorted(list(usable_idx_slice))  # got to always provide a sorted list of idx
        X = np.stack(self.x_dset[usable_idx_slice])
        y = np.stack(self.y_dset[usable_idx_slice])
        sw = np.stack(self.sw_dset[usable_idx_slice])

        if pool_size > 1:
            if y.shape[1] % pool_size != 0:
                # clip to maximum size possible with the pooling length
                overhang = y.shape[1] % pool_size
                X = X[:, :-overhang]
                y = y[:, :-overhang]
                sw = sw[:, :-overhang]

            X = X.reshape((
                X.shape[0],
                X.shape[1] // pool_size,
                -1
            ))
            # make labels 2d so we can use the standard softmax / loss functions
            y = y.reshape((
                y.shape[0],
                y.shape[1] // pool_size,
                pool_size,
                y.shape[-1],
            ))

            # mark any multi-base timestep as error if any base has an error
            sw = sw.reshape((sw.shape[0], -1, pool_size))
            sw = np.logical_not(np.any(sw == 0, axis=2)).astype(np.int8)

            if self.class_weights is not None:
                # class weights are only used during training and validation to keep the loss
                # comparable and are additive for the individual timestep predictions
                # giving even more weight to transition points
                # class weights without pooling not supported yet
                cls_arrays = [np.any((y[:, :, :, col] == 1), axis=2) for col in range(4)]
                cls_arrays = np.stack(cls_arrays, axis=2).astype(np.int8)
                # add class weights to applicable timesteps
                cw_arrays = np.multiply(cls_arrays, np.tile(self.class_weights, y.shape[:2] + (1,)))
                cw = np.sum(cw_arrays, axis=2)
                # multiply with previous sample weights
                sw = np.multiply(sw, cw)
        return X, y, sw


class LSTMModel(HelixerModel):
    def __init__(self):
        super().__init__()
        self.parser.add_argument('-u', '--units', type=int, default=4)
        self.parser.add_argument('-l', '--layers', type=int, default=1)
        self.parser.add_argument('-ps', '--pool-size', type=int, default=10)
        self.parser.add_argument('-ln', '--layer-normalization', action='store_true')
        self.parse_args()

    def sequence_cls(self):
        return LSTMSequence

    def model(self):
        model = Sequential()

        model.add(Bidirectional(
            CuDNNLSTM(self.units, return_sequences=True, input_shape=(None, self.pool_size * 4)),
            input_shape=(None, self.pool_size * 4)
        ))

        # potential next layers
        if self.layers > 1:
            for _ in range(self.layers - 1):
                if self.layer_normalization:
                    model.add(LayerNormalization())
                model.add(Bidirectional(CuDNNLSTM(self.units, return_sequences=True)))

        model.add(Dense(self.pool_size * 4))
        if self.pool_size > 1:
            model.add(Reshape((-1, self.pool_size, 4)))
        model.add(Activation('softmax'))
        return model

    def compile_model(self, model):
        model.compile(optimizer=self.optimizer,
                      loss='categorical_crossentropy',
                      sample_weight_mode='temporal')


if __name__ == '__main__':
    model = LSTMModel()
    model.run()
