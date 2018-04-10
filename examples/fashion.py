
from hyperopt import hp
import numpy as np
import logging

from protodata import datasets

from validation.tuning import tune_model
from training.policy import CyclicPolicy
from layout import cnn_kernel_example_layout_fn

CV_TRIALS = 5
SIM_RUNS = 5
MAX_EPOCHS = 300

n_layers = 3
name='fashion_mnist_alternate_%dl' % n_layers


logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=name,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s %(message)s',
)

if __name__ == '__main__':

    search_space = {
        # CNN params
        'cnn_filter_size': hp.choice('cnn_filter_size', [7, 9]),
        'map_size': 2 ** (6 + hp.randint('map_size', 2)),
        # CNN kernel params
        'cnn_kernel_size': 2 ** (7 + hp.randint('cnn_kernel_size_log2', 2)),
        # Shared kernel params
        'kernel_size': 2 ** (9 + hp.randint('kernel_size_log2', 2)),
        'kernel_std': hp.uniform('kernel_std_log10', 1e-2, 1.0),
        'hidden_units': 2 ** (8 + hp.randint('hidden_units_log2', 2)),
        # Training params
        'batch_size': 2 ** (4 + hp.randint('batch_size_log2', 2)),
        'l2_ratio': 10 ** hp.uniform('l2_log10', -5, -2),
        'lr': 10 ** hp.uniform('lr_log10', -5, -3),
        'lr_decay': hp.uniform('lr_decay', 0.1, 1.0),
        'lr_decay_epochs': hp.uniform('lr_decay_epochs', 20, 50),
        # ALT params
        'epochs_per_layer': 5 + hp.randint('epochs_per_layer', 10)
    }

    # Fixed parameters
    search_space.update({
        'image_specs': {
            'scale_size': 28,
            'crop_size': 28,
            'random_crop': False,
            'channels': 1,
            'isotropic': False,
            'mean': [0.0, 0.0, 0.0] # Already normalizing inputs during fit
        },
        'cnn_batch_norm': False,
        'batch_norm': True,
        'padding': 'VALID',
        'num_layers': n_layers,  # These are cnn layers here
        'progress_thresh': 0.1,
        'n_threads': 4,
        'memory_factor': 2,
        'max_epochs': MAX_EPOCHS,
        'strip_length': 5,
        'tune_folder': name + '_validate',
        'network_fn': cnn_kernel_example_layout_fn,
        'policy': {'switch_policy': CyclicPolicy},
        'fc_layers': 2,
        'stride': 1
    })

    stats = tune_model(
        dataset=datasets.Datasets.FASHION_MNIST,
        settings_fn=datasets.FashionMnistSettings,
        search_space=search_space,
        n_trials=CV_TRIALS,
        cross_validate=False,
        folder=name + '_stats',
        runs=SIM_RUNS,
        test_batch_size=128
    )

    metrics = stats[0].keys()
    for m in metrics:
        values = [x[m] for x in stats]
        logger.info('%s: %f +- %f' % (m, np.mean(values), np.std(values)))
