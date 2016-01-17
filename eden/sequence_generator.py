from eden.modifier.seq import seq_to_seq, shuffle_modifier
from eden.path import Vectorizer
from eden.util import fit, predict
import numpy as np
from itertools import combinations_with_replacement
import logging
logger = logging.getLogger(__name__)


class SequenceGenerator(object):

    def __init__(self, n_differences=1, enhance=True, vectorizer=Vectorizer(complexity=3), n_jobs=1):
        self.n_jobs = n_jobs
        self.n_differences = n_differences
        self.enhance = enhance
        if self.enhance is True:
            self.inhibit = False
        else:
            self.inhibit = True
        self.vectorizer = vectorizer
        self.estimator = None

    def fit(self, pos_seqs, neg_seqs=None):
        if neg_seqs is None:
            neg_seqs = list(seq_to_seq(pos_seqs, modifier=shuffle_modifier, times=2, order=2))
        self.estimator = fit(pos_seqs, neg_seqs, self.vectorizer,
                             n_jobs=self.n_jobs,
                             cv=10,
                             n_iter_search=1,
                             random_state=1,
                             n_blocks=5,
                             block_size=None)
        return self

    def sample(self, seqs, n_seqs=1, show_score=False):
        for seq in seqs:
            if show_score:
                preds = predict(iterable=[seq],
                                estimator=self.estimator,
                                vectorizer=self.vectorizer,
                                mode='decision_function', n_blocks=5, block_size=None, n_jobs=self.n_jobs)
                logger.debug('%s\n%+.3f %s' % (seq[0], preds[0], seq[1]))
            gen_seqs = self._generate(seq, n_seqs=n_seqs, show_score=show_score)
            for gen_seq in gen_seqs:
                yield gen_seq

    def _generate(self, input_seq, n_seqs=1, show_score=False):
        header, seq = input_seq
        # find best/worst n_differences positions
        seq_items, n_differences_ids = self._find_key_positions(seq)
        # replace all possible kmers of size n_differences
        gen_seqs = list(self._replace(seq_items, n_differences_ids))
        # keep the best/worst
        preds = predict(iterable=gen_seqs,
                        estimator=self.estimator,
                        vectorizer=self.vectorizer,
                        mode='decision_function', n_blocks=5, block_size=None, n_jobs=self.n_jobs)
        sorted_pred_ids = np.argsort(preds)
        if self.inhibit:
            n_seqs_ids = sorted_pred_ids[:n_seqs]
        else:
            n_seqs_ids = sorted_pred_ids[-n_seqs:]
        if show_score:
            return zip(np.array(preds)[n_seqs_ids], np.array(gen_seqs)[n_seqs_ids])
        else:
            return np.array(gen_seqs)[n_seqs_ids]

    def _replace(self, seq_items, n_differences_ids):
        alphabet = set(seq_items)
        kmers = combinations_with_replacement(alphabet, self.n_differences)
        for kmer in kmers:
            curr_seq = seq_items
            for i, symbol in enumerate(kmer):
                pos = n_differences_ids[i]
                curr_seq[pos] = symbol
            gen_seq = ''.join(curr_seq)
            yield gen_seq

    def _find_key_positions(self, seq):
        # annotate seq using estimator
        annotation = self.vectorizer.annotate([seq], estimator=self.estimator)
        seq_items, scores = annotation.next()
        assert(len(seq_items) == len(seq))
        assert(len(scores) == len(seq))
        sorted_ids = np.argsort(scores)
        if self.enhance:
            n_differences_ids = sorted_ids[:self.n_differences]
        else:
            n_differences_ids = sorted_ids[-self.n_differences:]
        return seq_items, n_differences_ids
