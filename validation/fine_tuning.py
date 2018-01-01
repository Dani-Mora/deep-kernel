import collections
import logging

from training.fit import DeepNetworkTraining

from protodata.utils import get_data_location

logger = logging.getLogger(__name__)


class FineTuningType(object):

    ExtraEpoch = collections.namedtuple(
        'ExtraEpochRefining', ['epochs']
    )

    ExtraLayerwise = collections.namedtuple(
        'ExtraLayerwise', ['epochs_per_layer', 'policy']
    )


def fine_tune_training(dataset,
                       settings_fn,
                       run_folder,
                       fine_tune,
                       num_layers,
                       **params):

    model = DeepNetworkTraining(
        settings_fn=settings_fn,
        data_location=get_data_location(dataset, folded=True),
        folder=run_folder
    )

    if isinstance(fine_tune, FineTuningType.ExtraLayerwise):

        logger.info(
            'Layerwise fine-tuning: training %d' % fine_tune.epochs_per_layer
            + ' epochs per layer using %s policy' % fine_tune.policy
        )

        switches = [
            fine_tune.epochs_per_layer * i
            for i in range(1, num_layers)
        ]

        print(switches)
        print(fine_tune.epochs_per_layer * num_layers)
        print(num_layers)

        return model.fit(
            num_layers=num_layers,
            max_epochs=fine_tune.epochs_per_layer * num_layers,
            switch_epochs=switches,
            switch_policy=fine_tune.policy,
            restore_folder=run_folder,
            **params
        )

    elif isinstance(fine_tune, FineTuningType.ExtraEpoch):

        logger.info(
            'Traditional fine-tuning: training %d' % fine_tune.epochs
            + ' extra epochs for the whole network'
        )

        print(params)

        return model.fit(
            num_layers=num_layers,
            max_epochs=fine_tune.epochs,
            restore_folder=run_folder,
            **params
        )

    else:
        raise ValueError('Unknown refining type {}'.format(fine_tune))
