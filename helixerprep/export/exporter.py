import os
import numpy as np
import intervaltree
import deepdish as dd

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import geenuff
from geenuff.base.orm import Coordinate, Genome
from geenuff.base.helpers import full_db_path
from .numerify import CoordNumerifier
from ..core.handlers import CoordinateHandler


class ExportController(object):
    def __init__(self, db_path_in, h5_path_out):
        self.db_path_in = db_path_in
        self.h5_path_out = h5_path_out
        self._mk_session()

    def _mk_session(self):
        self.engine = create_engine(full_db_path(self.db_path_in), echo=False)
        self.session = sessionmaker(bind=self.engine)()

    def export(self, chunk_size, shuffle, seed):
        """Fetches all Coordinates, calls on functions in numerify.py to split
        and encode them and then saves the (possibly shuffled) sequences to the
        specified .h5 file.
        """
        data = {
            'inputs': [],
            'labels': [],
            'label_masks': [],
            'config': {
                'chunk_size': chunk_size,
                'shuffle': shuffle,
                'seed': seed,
            },
        }
        all_coords = self.session.query(Coordinate).all()
        for coord in all_coords:
            for is_plus_strand in [True, False]:
                coord_handler = CoordinateHandler(coord)
                numerifier = CoordNumerifier(coord_handler, is_plus_strand, chunk_size)
                coord_data = numerifier.numerify()
                for key in ['inputs', 'labels', 'label_masks']:
                    data[key] += coord_data[key]

        # only works if all arrays in the list are of the same size
        # data['input'] = np.array(data['input'])
        # data['labels'] = np.array(data['labels'])
        dd.io.save(self.h5_path_out, data, compression=None)