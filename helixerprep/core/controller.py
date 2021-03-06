import os
import csv
from shutil import copyfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import geenuff
from geenuff.base.helpers import full_db_path, reverse_complement
from geenuff.base.orm import Coordinate, Genome
from helixerprep.core.orm import Mer, MetaInformation


class HelixerController(object):
    def __init__(self, db_path_in, db_path_out, meta_info_root_path, meta_info_csv_path):
        self.meta_info_root_path = meta_info_root_path
        self.meta_info_csv_path = meta_info_csv_path
        self._setup_db(db_path_in, db_path_out)
        self._mk_session()

    def _setup_db(self, db_path_in, db_path_out):
        self.db_path = db_path_out
        if db_path_out != '':
            if os.path.exists(db_path_out):
                print('overriding the helixer output db at {}'.format(db_path_out))
            copyfile(db_path_in, db_path_out)
        else:
            print('adding the helixer additions directly to input db at {}'.format(db_path_in))
            self.db_path = db_path_in

    def _mk_session(self):
        self.engine = create_engine(full_db_path(self.db_path), echo=False)
        # add Helixer specific tables to the input db if they don't exist yet
        new_tables = ['mer', 'meta_information']
        for table in new_tables:
            if not self.engine.dialect.has_table(self.engine, table):
                geenuff.orm.Base.metadata.tables[table].create(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def _add_mers_of_seqid(self, species, seqid, mers):
        print(species, seqid)
        genome_id = self.session.query(Genome.id).filter(Genome.species == species).one()[0]
        coord_id = (self.session.query(Coordinate.id)
                       .filter(Coordinate.genome_id == genome_id)
                       .filter(Coordinate.seqid == seqid)
                       .one())[0]
        for mer_sequence, count in mers.items():
            mer = Mer(coordinate_id=coord_id,
                      mer_sequence=mer_sequence,
                      count=count,
                      length=len(mer_sequence))
            self.session.add(mer)
        self.session.commit()

    def add_mer_counts_to_db(self):
        """Tries to add all kmer counts it can find for each coordinate in the db
        Assumes the kmer file to contain non-collapsed kmers ordered by coordinate first and kmer
        sequence second"""
        genomes_in_db = self.session.query(Genome).all()
        for i, genome in enumerate(genomes_in_db):
            kmer_file = os.path.join(self.meta_info_root_path, genomes_in_db[i].species,
                                     'meta_collection', 'kmers', 'kmers.tsv')
            if os.path.exists(kmer_file):
                last_seqid = ''
                seqid_mers = {}  # here we collect the sum of the
                for i, line in enumerate(open(kmer_file)):
                    # loop setup
                    if i == 0:
                        continue  # skip header
                    seqid, mer_sequence, count, _ = line.strip().split('\t')
                    count = int(count)
                    if i == 1:
                        last_seqid = seqid

                    # insert coordinate mers
                    if last_seqid != seqid:
                        self._add_mers_of_seqid(genome.species, last_seqid, seqid_mers)
                        seqid_mers = {}
                        last_seqid = seqid

                    # figure out kmer collapse
                    rc = ''.join(reverse_complement(mer_sequence))
                    key = rc if rc < mer_sequence else mer_sequence
                    if key in seqid_mers:
                        seqid_mers[key] += count
                    else:
                        seqid_mers[key] = count
                self._add_mers_of_seqid(genome.species, last_seqid, seqid_mers)
                print('Kmers from file {} added\n'.format(kmer_file))

    def add_meta_info_to_db(self):
        """For each genome found in the db, the function tries to insert meta data from the
        csv file into the meta_information table."""
        with open(self.meta_info_csv_path) as f:
            reader = csv.reader(f)
            header = next(reader)
            meta_data = list(reader)
        species_i = [i for i in range(len(header)) if header[i] == "species"][0]
        genomes_in_db = self.session.query(Genome).all()
        for genome in genomes_in_db:
            genome_meta_info = [row for row in meta_data if row[species_i] == genome.species][0]
            if len(genome_meta_info) > 0:
                for key, value in zip(header, genome_meta_info):
                    if key != 'species':
                        meta_info = MetaInformation(genome=genome, name=key, value=value)
                        self.session.add(meta_info)
                print('Meta info added for {}'.format(genome.species))
            else:
                print('Meta info not found for {}'.format(genome.species))
        self.session.commit()
