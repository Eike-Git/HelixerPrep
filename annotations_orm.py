import enum
import type_enums

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, ForeignKey, String, Enum, CheckConstraint, Boolean, Float
from sqlalchemy.orm import relationship

# setup classes for data holding
Base = declarative_base()


class AnnotatedGenome(Base):
    __tablename__ = 'annotated_genomes'

    # data
    id = Column(Integer, primary_key=True)
    species = Column(String)
    accession = Column(String)
    version = Column(String)
    acquired_from = Column(String)
    sequence_infos = relationship("SequenceInfo", back_populates="annotated_genome")


class ProcessingSet(enum.Enum):
    train = 'train'
    dev = 'dev'
    test = 'test'


class SequenceInfo(Base):
    __tablename__ = "sequence_infos"

    id = Column(Integer, primary_key=True)
    # relations
    annotated_genome_id = Column(Integer, ForeignKey('annotated_genomes.id'), nullable=False)
    annotated_genome = relationship('AnnotatedGenome', back_populates="sequence_infos")
    processing_set = Column(Enum(ProcessingSet))
    coordinates = relationship('Coordinates', back_populates="sequence_info")
    super_loci = relationship('SuperLocus', back_populates="sequence_info")


class Coordinates(Base):
    __tablename__ = 'coordinates'

    id = Column(Integer, primary_key=True)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    seqid = Column(String, nullable=False)
    sequence_info_id = Column(Integer, ForeignKey('sequence_infos.id'))
    sequence_info = relationship('SequenceInfo', back_populates='coordinates')

    __table_args__ = (
        CheckConstraint(start >= 1, name='check_start_1plus'),
        CheckConstraint(end >= start, name='check_end_gr_start'),
        {})


class SuperLocusAliases(Base):
    __tablename__ = 'super_locus_aliases'

    id = Column(Integer, primary_key=True)
    alias = Column(String)
    super_locus_id = Column(Integer, ForeignKey('super_loci.id'))
    super_locus = relationship('SuperLocus', back_populates='aliases')


class SuperLocus(Base):
    __tablename__ = 'super_loci'
    # normally a loci, some times a short list of loci for "trans splicing"
    # this will define a group of exons that can possibly be made into transcripts
    # AKA this if you have to go searching through a graph for parents/children, at least said graph will have
    # a max size defined at SuperLoci

    id = Column(Integer, primary_key=True)
    given_id = Column(String)
    type = Column(Enum(type_enums.SuperLocusAll))
    # relations
    sequence_info_id = Column(Integer, ForeignKey('sequence_infos.id'))
    sequence_info = relationship('SequenceInfo', back_populates='super_loci')
    # things SuperLocus can have a lot of
    aliases = relationship('SuperLocusAliases', back_populates='super_locus')
    features = relationship('Feature', back_populates='super_locus')
    transcribeds = relationship('Transcribed', back_populates='super_locus')
    translateds = relationship('Translated', back_populates='super_locus')


association_transcribeds_to_features = Table('association_transcribeds_to_features', Base.metadata,
    Column('transcribed_id', Integer, ForeignKey('transcribeds.id')),
    Column('feature_id', Integer, ForeignKey('features.id'))
)

association_translateds_to_features = Table('association_translateds_to_features', Base.metadata,
    Column('translated_id', Integer, ForeignKey('translateds.id')),
    Column('feature_id', Integer, ForeignKey('features.id'))
)

association_translateds_to_transcribeds = Table('association_translateds_to_transcribeds', Base.metadata,
    Column('translated_id', Integer, ForeignKey('translateds.id')),
    Column('transcribed_id', Integer, ForeignKey('transcribeds.id'))
)


class Transcribed(Base):
    __tablename__ = 'transcribeds'

    id = Column(Integer, primary_key=True)
    given_id = Column(String)
    type = Column(Enum(type_enums.TranscriptLevelAll))

    super_locus_id = Column(Integer, ForeignKey('super_loci.id'))
    super_locus = relationship('SuperLocus', back_populates='transcribeds')

    features = relationship('Feature', secondary=association_transcribeds_to_features,
                            back_populates='transcribeds')

    translateds = relationship('Translated', secondary=association_translateds_to_transcribeds,
                               back_populates='transcribeds')



class Translated(Base):
    __tablename__ = 'translateds'

    id = Column(Integer, primary_key=True)
    given_id = Column(String)
    # type can only be 'protein' so far as I know..., so skipping
    super_locus_id = Column(Integer, ForeignKey('super_loci.id'))
    super_locus = relationship('SuperLocus', back_populates='translateds')

    features = relationship('Feature', secondary=association_translateds_to_features,
                            back_populates='translateds')

    transcribeds = relationship('Transcribed', secondary=association_translateds_to_transcribeds,
                                back_populates='translateds')


class Feature(Base):
    __tablename__ = 'features'
    # basic attributes
    id = Column(Integer, primary_key=True)
    given_id = Column(String)

    type = Column(Enum(type_enums.OnSequence))
    seqid = Column(String)
    start = Column(Integer)
    end = Column(Integer)
    is_plus_strand = Column(Boolean)
    score = Column(Float)
    source = Column(String)
    phase = Column(Integer)

    # for differentiating from subclass entries
    subtype = Column(String(20))
    # relations
    super_locus_id = Column(Integer, ForeignKey('super_loci.id'))
    super_locus = relationship('SuperLocus', back_populates='features')

    transcribeds = relationship('Transcribed', secondary=association_transcribeds_to_features,
                                back_populates='features')

    translateds = relationship('Translated', secondary=association_translateds_to_features,
                               back_populates='features')

    __table_args__ = (
        CheckConstraint(start >= 1, name='check_start_1plus'),
        CheckConstraint(end >= start, name='check_end_gr_start'),
        CheckConstraint(phase >= 0, name='check_phase_not_negative'),
        CheckConstraint(phase < 3, name='check_phase_less_three'),
        {})

    __mapper_args__ = {
        'polymorphic_on': subtype,
        'polymorphic_identity': 'general'
    }


class DownstreamFeature(Feature):
    __tablename__ = 'downstream_features'

    id = Column(Integer, ForeignKey('features.id'), primary_key=True)
    upstream_id = Column(Integer, ForeignKey('upstream_features.id'))
    upstream = relationship('UpstreamFeature', back_populates="downstream", foreign_keys=[upstream_id])

    __mapper_args__ = {
        'polymorphic_identity': 'downstream'
    }


class UpstreamFeature(Feature):
    __tablename__ = 'upstream_features'

    id = Column(Integer, ForeignKey('features.id'), primary_key=True)
    downstream = relationship('DownstreamFeature', uselist=False, back_populates='upstream',
                              foreign_keys=[DownstreamFeature.upstream_id])
    __mapper_args__ = {
        'polymorphic_identity': 'upstream'
    }