#!/usr/bin/env python
"""Provides scikit interface."""

import numpy as np
from eden.graph import vectorize
from eden.util import timeit
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import SGDClassifier
from sklearn.linear_model import Perceptron
import dask_searchcv as dcv
from sklearn.model_selection import learning_curve
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import cross_val_predict
from dask.diagnostics import Profiler, ResourceProfiler, CacheProfiler
from dask.diagnostics import visualize
import multiprocessing as mp
from eden.estimator_utils import balance, subsample, paired_shuffle
import random
import logging

logger = logging.getLogger()


class EdenEstimator(BaseEstimator, ClassifierMixin):
    """Build an estimator for graphs."""

    def __init__(self, r=3, d=8, nbits=16, n_jobs=-1, discrete=True,
                 balance=False, subsample_size=200, ratio=2,
                 normalization=False, inner_normalization=False,
                 penalty='elasticnet', n_iter=500):
        """construct."""
        self.set_params(r, d, nbits, n_jobs, discrete, balance, subsample_size,
                        ratio, normalization, inner_normalization,
                        penalty, n_iter)

    def set_params(self, r=3, d=8, nbits=16, n_jobs=-1, discrete=True,
                   balance=False, subsample_size=200, ratio=2,
                   normalization=False, inner_normalization=False,
                   penalty='elasticnet', n_iter=500):
        """setter."""
        self.r = r
        self.d = d
        self.nbits = nbits
        self.n_jobs = n_jobs
        self.normalization = normalization
        self.inner_normalization = inner_normalization
        self.discrete = discrete
        self.balance = balance
        self.subsample_size = subsample_size
        self.ratio = ratio
        if penalty == 'perceptron':
            self.model = Perceptron(n_iter=n_iter)
        else:
            self.model = SGDClassifier(
                average=True, class_weight='balanced', shuffle=True,
                penalty=penalty)
        return self

    def transform(self, graphs):
        """transform."""
        x = vectorize(
            graphs, r=self.r, d=self.d,
            normalization=self.normalization,
            inner_normalization=self.inner_normalization,
            discrete=self.discrete,
            nbits=self.nbits,
            n_jobs=self.n_jobs)
        return x

    @timeit
    def fit(self, graphs, targets, randomize=True):
        """fit."""
        if self.balance:
            if randomize:
                bal_graphs, bal_targets = balance(
                    graphs, targets, None, ratio=self.ratio)
            else:
                samp_graphs, samp_targets = subsample(
                    graphs, targets, subsample_size=self.subsample_size)
                x = self.transform(samp_graphs)
                self.model.fit(x, samp_targets)
                bal_graphs, bal_targets = balance(
                    graphs, targets, self, ratio=self.ratio)
            size = len(bal_targets)
            logger.debug('Dataset size=%d' % (size))
            x = self.transform(bal_graphs)
            self.model = self.model.fit(x, bal_targets)
        else:
            x = self.transform(graphs)
            self.model = self.model.fit(x, targets)
        return self

    @timeit
    def predict(self, graphs):
        """predict."""
        x = self.transform(graphs)
        preds = self.model.predict(x)
        return preds

    @timeit
    def decision_function(self, graphs):
        """decision_function."""
        x = self.transform(graphs)
        preds = self.model.decision_function(x)
        return preds

    @timeit
    def cross_val_score(self, graphs, targets,
                        scoring='roc_auc', cv=5):
        """cross_val_score."""
        x = self.transform(graphs)
        scores = cross_val_score(
            self.model, x, targets, cv=cv,
            scoring=scoring, n_jobs=self.n_jobs)
        return scores

    @timeit
    def cross_val_predict(self, graphs, targets, cv=5):
        """cross_val_score."""
        x = self.transform(graphs)
        scores = cross_val_predict(
            self.model, x, targets, cv=cv, method='decision_function')
        return scores

    @timeit
    def model_selection(self, graphs, targets, subsample_size=None):
        """model_selection."""
        return self._model_selection(
            graphs, targets, None, subsample_size, mode='grid')

    @timeit
    def model_selection_rand(self, graphs, targets,
                             n_iter=30, subsample_size=None):
        """model_selection_randomized."""
        param_distr = {"r": list(range(1, 5)), "d": list(range(0, 10))}
        if subsample_size:
            graphs, targets = subsample(
                graphs, targets, subsample_size=subsample_size)

        pool = mp.Pool()
        scores = pool.map(_eval, [(graphs, targets, param_distr)] * n_iter)
        pool.close()
        pool.join()

        best_params = max(scores)[1]
        logger.debug("Best parameters:\n%s" % (best_params))
        self = EdenEstimator(**best_params)
        return self

    def _model_selection(self, graphs, targets, n_iter=30,
                         subsample_size=None, mode='randomized'):
        with Profiler() as prof, ResourceProfiler(dt=0.25) as rprof, CacheProfiler() as cprof:
            param_distr = {"r": list(range(1, 4)), "d": list(range(0, 5))}
            if mode == 'randomized':
                search = dcv.RandomizedSearchCV(
                    self, param_distr, cv=3, n_iter=n_iter)
            else:
                search = dcv.GridSearchCV(
                    self, param_distr, cv=3)
            if subsample_size:
                graphs, targets = subsample(
                    graphs, targets, subsample_size=subsample_size)
            search = search.fit(graphs, targets)
            logger.debug("Best parameters:\n%s" % (search.best_params_))
            self = search.best_estimator_
            self.r = search.best_params_['r']
            self.d = search.best_params_['d']
            visualize([prof, rprof, cprof])
        return self

    @timeit
    def learning_curve(self, graphs, targets,
                       cv=5, n_steps=10, start_fraction=0.1):
        """learning_curve."""
        graphs, targets = paired_shuffle(graphs, targets)
        x = self.transform(graphs)
        train_sizes = np.linspace(start_fraction, 1.0, n_steps)
        scoring = 'roc_auc'
        train_sizes, train_scores, test_scores = learning_curve(
            self.model, x, targets,
            cv=cv, train_sizes=train_sizes,
            scoring=scoring, n_jobs=self.n_jobs)
        return train_sizes, train_scores, test_scores

    def bias_variance_decomposition(self, graphs, targets,
                                    cv=5, n_bootstraps=10):
        """bias_variance_decomposition."""
        x = self.transform(graphs)
        score_list = []
        for i in range(n_bootstraps):
            scores = cross_val_score(
                self.model, x, targets, cv=cv,
                n_jobs=self.n_jobs)
            score_list.append(scores)
        score_list = np.array(score_list)
        mean_scores = np.mean(score_list, axis=1)
        std_scores = np.std(score_list, axis=1)
        return mean_scores, std_scores


def _sample_params(param_distr):
    params = dict()
    for key in param_distr:
        params[key] = random.choice(param_distr[key])
    return params


def _eval_params(graphs, targets, param_distr):
    # sample parameters
    params = _sample_params(param_distr)
    # create model with those parameters
    est = EdenEstimator(n_jobs=1, **params)
    # run a cross_val_score
    scores = est.cross_val_score(graphs, targets)
    # return average
    return np.mean(scores), params


def _eval(data):
    return _eval_params(*data)
