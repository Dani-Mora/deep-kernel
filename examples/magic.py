from hyperopt import hp
import numpy as np
import logging

from protodata import datasets

from validation.tuning import tune_model
from validation.fine_tuning import FineTuningType
from training.policy import CyclicPolicy

CV_TRIALS = 25
SIM_RUNS = 10
MAX_EPOCHS = 10000

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
)

if __name__ == '__main__':

    search_space = {
        'batch_size': hp.choice('batch_size', [128]),
        'l2_ratio': hp.choice('l2_ratio', [0, 1e-1, 1e-2, 1e-3, 1e-4]),
        'lr': hp.choice('lr', [1e-2, 1e-3, 1e-4]),
        'kernel_size': hp.choice('kernel_size', [64, 128, 256, 512]),
        'kernel_std': hp.choice('kernel_std', [1e-2, 0.1, 0.25, 0.5, 1.0]),
        'hidden_units': hp.choice('hidden_units', [512, 1024, 2048])
    }

    # Fixed parameters
    search_space.update({
        'max_layers': 1,
        'lr_decay': 0.5,
        'lr_decay_epocs': 250,
        'n_threads': 4,
        'memory_factor': 2,
        'max_epochs': MAX_EPOCHS,
        'strip_length': 5,
        'progress_thresh': 0.1,
        'kernel_mean': 0.0,
    })

    stats = tune_model(
        dataset=datasets.Datasets.MAGIC,
        settings_fn=datasets.MagicSettings,
        search_space=search_space,
        n_trials=CV_TRIALS,
        cross_validate=False,
        folder='magic',
        runs=SIM_RUNS,
        test_batch_size=1,
        fine_tune=FineTuningType.ExtraLayerwise(
            epochs_per_layer=20, policy=CyclicPolicy
        )
    )

    metrics = stats[0].keys()
    for m in metrics:
        values = [x[m] for x in stats]
        logger.info('%s: %f +- %f' % (m, np.mean(values), np.std(values)))
