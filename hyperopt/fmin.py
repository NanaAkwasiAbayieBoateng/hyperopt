import numpy as np

import pyll

import base

class _FBandit(base.Bandit):
    def __init__(self, f, domain, **kwargs):
        self.f = f
        self.domain = domain
        base.Bandit.__init__(self, domain, **kwargs)

    def evaluate(self, config, ctrl):
        memo = self.memo_from_config(config)
        memo[self.pyll_ctrl] = ctrl
        if self.rng is not None and not self.installed_rng:
            # -- N.B. this modifies the expr graph in-place
            #    XXX this feels wrong
            self.expr = recursive_set_rng_kwarg(self.expr,
                pyll.as_apply(self.rng))
            self.installed_rng = True
        try:
            # -- the "work" of evaluating `config` can be written
            #    either into the pyll part (self.expr)
            #    or the normal Python part (self.f)
            pyll_rval = pyll.rec_eval(self.expr, memo=memo)
            rval = self.f(pyll_rval)
        except Exception, e:
            n_match = 0
            for match, match_pair in self.exceptions:
                if match(e):
                    pyll_rval = match_pair(e)
                    n_match += 1
                    break
            if n_match == 0:
                raise

        if isinstance(rval, (float, int, np.number)):
            dict_rval = {'loss': rval}
        elif isinstance(rval, (dict,)):
            dict_rval = rval
            if 'loss' not in dict_rval:
                raise ValueError('dictionary must have "loss" key',
                        dict_rval.keys())
        else:
            raise TypeError('invalid return type (neither number nor dict)', rval)

        if dict_rval['loss'] is not None:
            # -- fail if cannot be cast to float
            dict_rval['loss'] = float(dict_rval['loss'])

        dict_rval.setdefault('status', base.STATUS_OK)
        if dict_rval['status'] not in base.STATUS_STRINGS:
            raise ValueError('invalid status string', dict_rval['status'])

        return dict_rval

    def short_str(self):
        return 'FBandit{%s}' % str(self.f)


class FMinBase(object):
    def __init__(self, f, domain, trials, algo, async=None):
        self.f = f
        self.domain = domain
        self.trials = trials
        self.experiment = base.Experiment(trials, algo, async)
        self.experiment.catch_bandit_exceptions = False

    def __iter__(self):
        return self

    def next(self):
        self.experiment.run(1, block_until_done=self.experiment.async)
        return self.trials._dynamic_trials[-1]

    def exhaust(self):
        for foo in self:
            pass
        self.trials.refresh()
        return self

    @property
    def argmin(self):
        self.trials.refresh()
        results = self.trials.results
        miscs = self.trials.miscs
        best = np.argmin([r['loss'] for r in results])
        vals = self.trials.miscs[best]['vals']
        # unpack the one-element lists to values
        # and skip over the 0-element lists
        # TODO: move this logic to some more global place
        rval = {}
        for k, v in vals.items():
            if v:
                rval[k] = v[0]
        return rval

