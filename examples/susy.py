from hyperopt import hp
import numpy as np
import logging

from protodata import datasets

from validation.tuning import tune_model
from training.policy import CyclicPolicy, InverseCyclingPolicy, RandomPolicy
from layout import kernel_example_layout_fn

CV_TRIALS = 5
SIM_RUNS = 10
MAX_EPOCHS = 10000

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename='susy_baseline.log',
    level=logging.INFO
)


if __name__ == '__main__':

    search_space = {
        'batch_size': 2 ** (6 + hp.randint('batch_size_log2', 2)),
        'l2_ratio': 10 ** hp.uniform('l2_log10', -5, -2),
        'lr': 10 ** hp.uniform('lr_log10', -5, -3),
        'kernel_size': 2 ** (8 + hp.randint('kernel_size_log2', 3)),
        'kernel_std': hp.uniform('kernel_std_log10', 1e-2, 1.0),
        'hidden_units': 2 ** (9 + hp.randint('hidden_units_log2', 3)),
        'lr_decay': hp.uniform('lr_decay', 0.1, 1.0),
        'lr_decay_epochs': hp.uniform('lr_decay_epochs', 20, 40),
        # Comment next lines for non-layerwise training
        'policy': hp.choice('policy', [
            {
                'switch_policy': CyclicPolicy
            },
            {
                'switch_policy': InverseCyclingPolicy
            },
            {
                'switch_policy': RandomPolicy,
                'policy_seed': hp.randint('seed', 10000)
            }
        ])
    }

    # Fixed parameters
    search_space.update({
        'num_layers': 1,
        'layerwise_progress_thresh': 0.1,
        'n_threads': 4,
        'memory_factor': 2,
        'max_epochs': MAX_EPOCHS,
        'strip_length': 5,
        'progress_thresh': 0.1,
        'network_fn': kernel_example_layout_fn
    })

    stats = tune_model(
        dataset=datasets.Datasets.SUSY,
        settings_fn=datasets.SusySettings,
        search_space=search_space,
        n_trials=CV_TRIALS,
        cross_validate=False,
        layerwise=False,
        folder='susy',
        runs=SIM_RUNS,
        test_batch_size=128
    )

    metrics = stats[0].keys()
    for m in metrics:
        values = [x[m] for x in stats]
        logger.info('%s: %f +- %f' % (m, np.mean(values), np.std(values)))
