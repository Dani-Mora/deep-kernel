import tensorflow as tf
import numpy as np

import logging
import collections

from layout import kernel_example_layout_fn
from ops import get_model_weights, loss_ops_list, get_accuracy_op, \
                train_ops_list, get_l2_ops_list, progress

from protodata.data_ops import DataMode

logger = logging.getLogger(__name__)


RunContext = collections.namedtuple(
    'RunContext',
    [
        'logits_op', 'train_ops', 'loss_ops', 'acc_op',
        'steps_per_epoch', 'l2_ops', 'lr_op'
    ]
)


class EarlyStop(object):

    def __init__(self, name, progress_thresh, max_succ_errors):
        self._name = name
        self._train_errors = []
        self._prev_val_error = float('inf')
        self._successive_errors = 1
        self._progress_thresh = progress_thresh
        self._max_succ_errors = max_succ_errors

        self._best = {'val_error': float('inf')}
        self._succ_fails = 0

    def epoch_update(self, train_error):
        self._train_errors.append(train_error)

    def strip_update(self,
                     train_error,
                     train_loss,
                     val_error,
                     val_loss,
                     epoch):
        best_found, stop = False, False

        # Track best model at validation
        if self._best['val_error'] > val_error:
            logger.debug('[%s, %d] New best found' % (self._name, epoch))

            best_found = True
            self._best = {
                'val_loss': val_loss,
                'val_error': val_error,
                'epoch': epoch,
                'train_loss': train_loss,
                'train_error': train_error,
            }

        # Stop using progress criteria
        train_progress = progress(self._train_errors)
        if train_progress < self._progress_thresh:
            logger.debug(
                '[%s, %d] Stuck in training due to ' % (self._name, epoch) +
                'lack of progress (%f < %f). Halting...'
                % (train_progress, self._progress_thresh)
            )
            stop = True

        # Stop using UP criteria
        if self._prev_val_error < val_error:
            self._succ_fails += 1
            logger.debug(
                '[%s, %d] Validation error increase. ' % (self._name, epoch) +
                'Successive fails: %d' % self._succ_fails
            )
        else:
            self._succ_fails = 0

        if self._succ_fails == self._max_succ_errors:
            logger.debug(
                '[%s, %d] Validation error increased ' % (self._name, epoch) +
                'for %d successive times. Halting ...' % self._max_succ_errors
            )
            stop = True

        self._prev_val_error = val_error
        train_errors = self._train_errors.copy()
        self._train_errors = []

        return best_found, stop, train_errors

    def set_zero_fails(self):
        self._succ_fails = 0

    def get_best(self):
        return self._best


class RunStatus(object):

    def __init__(self):
        self.loss, self.acc, self.l2 = [], [], []

    def update(self, loss, acc, l2):
        self.loss.append(loss)
        self.acc.append(acc)
        self.l2.append(l2)

    def clear(self):
        self.loss, self.acc, self.l2 = [], [], []

    def get_means(self):
        return np.mean(self.loss), np.mean(self.acc), np.mean(self.l2)


def run_training_epoch_debug_weights(sess, context, layer_idx, num_layers):
    status = RunStatus()

    logger.debug('Running training epoch on {} variables'.format(layer_idx))

    weight_ops = []
    for i in range(1, num_layers + 1):
        if i == num_layers:
            include_output = True
        else:
            include_output = False

        current_weights = get_model_weights([i], include_output)

        for weight in current_weights:
            logger.info('Adding %s' % weight.name)
            weight_ops.append(weight)

    for i in range(context.steps_per_epoch):
        results = sess.run(
            [
                context.train_ops[layer_idx],
                context.loss_ops[layer_idx],
                context.acc_op,
                context.l2_ops[layer_idx],
            ] + weight_ops
        )

        _, loss, acc, l2 = results[:4]
        weights = results[4:]

        for i, w in enumerate(weights):
            trained = '[Trained]' if i + 1 == layer_idx or layer_idx == 0 \
                else ''
            logger.info(
                'First value layer %d %.10f %s\n'
                % (i + 1, w[0, 0], trained)
            )
        logger.info('Ended step\n')

        status.update(loss, acc, l2)

    return status.get_means()


def run_training_epoch_debug_l2(sess, context, layer_idx, num_layers):
    status = RunStatus()

    logger.debug('Running training epoch on {} variables'.format(layer_idx))

    l2_ops = [context.l2_ops[i] for i in range(0, num_layers+1)]

    for i in range(context.steps_per_epoch):
        results = sess.run(
            [
                context.train_ops[layer_idx],
                context.loss_ops[layer_idx],
                context.acc_op,
                context.l2_ops[layer_idx],
            ] + l2_ops
        )

        _, loss, acc, l2_truth = results[:4]
        l2_results = results[4:]

        for i, l2 in enumerate(l2_results):
            trained = '[Trained]' if i == layer_idx or layer_idx == 0 \
                else ''
            num = str('layer %d + output' % i) if i != 0 else 'all'
            logger.info(
                'L2 {0:20} {1:.8f} {2}'.format(
                    num, l2, trained
                )
            )

        out_l2 = (np.sum(l2_results[1:]) - l2_results[0])/(num_layers-1)
        logger.info(
            'L2 {0:20} {1:.8f} [Trained]'.format(
                'output_layer', out_l2
            )
        )
        logger.info('Ended step\n')

        status.update(loss, acc, l2_truth)

    return status.get_means()


def run_training_epoch(sess, context, layer_idx):
    status = RunStatus()

    logger.debug('Running training epoch on {} variables'.format(layer_idx))

    for i in range(context.steps_per_epoch):
        _, loss, acc, l2 = sess.run(
            [
                context.train_ops[layer_idx],
                context.loss_ops[layer_idx],
                context.acc_op,
                context.l2_ops[layer_idx]
            ]
        )
        status.update(loss, acc, l2)

    return status.get_means()


def eval_epoch(sess, context, layer_idx):
    status = RunStatus()

    for _ in range(context.steps_per_epoch):
        loss, acc, l2 = sess.run(
            [
                context.loss_ops[layer_idx],
                context.acc_op,
                context.l2_ops[layer_idx]
            ]
        )

        status.update(loss, acc, l2)

    return status.get_means()


def build_run_context(dataset,
                      reader,
                      tag,
                      folds,
                      step,
                      reuse=False,
                      is_training=True,
                      **params):
    lr = params.get('lr', 0.01)
    lr_decay = params.get('lr_decay', 0.5)
    lr_decay_epocs = params.get('lr_decay_epochs', 500)
    network_fn = params.get('network_fn', kernel_example_layout_fn)
    batch_size = params.get('batch_size')
    memory_factor = params.get('memory_factor')
    n_threads = params.get('n_threads')
    n_layers = params.get('num_layers')

    if folds is not None:
        fold_size = dataset.get_fold_size()
        steps_per_epoch = int(fold_size * len(folds) / batch_size)
        lr_decay_steps = lr_decay_epocs * steps_per_epoch
    else:
        steps_per_epoch = None
        lr_decay_steps = 10000  # Default value, not used

    data_subset = DataMode.TRAINING if tag == DataMode.VALIDATION else tag
    features, labels = reader.read_folded_batch(
        batch_size=batch_size,
        data_mode=data_subset,
        folds=folds,
        memory_factor=memory_factor,
        reader_threads=n_threads,
        train_mode=is_training,
        shuffle=True
    )

    scope_params = {'reuse': reuse}
    with tf.variable_scope("network", **scope_params):

        logits = network_fn(features,
                            columns=dataset.get_wide_columns(),
                            outputs=dataset.get_num_classes(),
                            tag=tag,
                            is_training=is_training,
                            **params)

        loss_ops = loss_ops_list(
            logits=logits,
            y=labels,
            sum_collection=tag,
            n_classes=dataset.get_num_classes(),
            **params
        )

        if is_training:

            # Decaying learning rate: lr(t)' = lr / (1 + decay * t)
            lr_op = tf.train.inverse_time_decay(
                lr, step, decay_steps=lr_decay_steps, decay_rate=lr_decay
            )

            train_ops = train_ops_list(step, lr_op, loss_ops, n_layers)
        else:
            train_ops, lr_op = None, None

        # Evaluate model
        accuracy_op = get_accuracy_op(
            logits, labels, dataset.get_num_classes()
        )

    return RunContext(
        logits_op=logits,
        train_ops=train_ops,
        loss_ops=loss_ops,
        lr_op=lr_op,
        acc_op=accuracy_op,
        steps_per_epoch=steps_per_epoch,
        l2_ops=get_l2_ops_list(**params)
    )
