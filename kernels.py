import abc
import random

import numpy as np
import tensorflow as tf

KERNEL_COLLECTION = 'KERNEL_VARS'
KERNEL_ASSIGN_OPS = 'KERNEL_ASSIGN_OPS'


class RandomFourierFeatures(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, name, input_dims, kernel_size):
        self._name = name
        self._input_dims = input_dims
        self._kernel_size = kernel_size

    @abc.abstractmethod
    def draw_samples(self, input_size, rff_features):
        """
        Draws samples according to the corresponding Fourier distribution
        """

    def apply_kernel(self, x, tag):

        w_name = '_'.join([self._name, 'w'])  # Name is important, dont change
        b_name = '_'.join([self._name, 'b'])  # Name is important, dont change

        # Create variable
        w = tf.get_variable(
            w_name,
            [self._kernel_size, self._input_dims],
            trainable=False,  # Important: this is constant!,
            collections=[KERNEL_COLLECTION, tf.GraphKeys.GLOBAL_VARIABLES]
        )

        b = tf.get_variable(
            b_name,
            [self._kernel_size],
            trainable=False,
            collections=[KERNEL_COLLECTION, tf.GraphKeys.GLOBAL_VARIABLES]
        )

        w_value, b_value = self.draw_samples()

        tf.add_to_collection(KERNEL_ASSIGN_OPS, w.assign(w_value))
        tf.add_to_collection(KERNEL_ASSIGN_OPS, b.assign(b_value))

        # Let's store the RFF so we have it if needed
        self._w = w
        self._b = b

        # Check: see matrix does not change with time
        tf.summary.histogram(w_name, w, [tag])
        tf.summary.histogram(b_name, b, [tag])

        # Check: input to be centered around 0
        dot = tf.add(tf.matmul(x, tf.transpose(w)), b)
        tf.summary.histogram(self._name + '_dot', dot, [tag])

        # Difference from orifinal paper: empirical results show that
        # by diving by a constant at each step we make the output of each
        # progressively decrease and therefore and we get much higher error
        z = tf.cos(dot) * np.sqrt(2/self._kernel_size)
        tf.summary.histogram(self._name + '_z', z, [tag])

        return z


class GaussianRFF(RandomFourierFeatures):

    def __init__(self, name, input_dims, kernel_size=32, mean=0.0, std=1.0):
        super(GaussianRFF, self).__init__(
            name, input_dims, kernel_size
        )
        self._mean = mean
        self._std = std

    def draw_samples(self):
        # Credits to sampling to hichamjanati
        # https://github.com/hichamjanati/srf/blob/master/RFF.py
        w = np.sqrt(2*self._std)*np.random.normal(
            size=[self._kernel_size, self._input_dims]
        )
        '''
        # Previous
        w = np.random.normal(
            self._mean,
            self._std,
            [self._kernel_size, self._input_dims]
        )
        '''
        b = [random.uniform(0, 2*np.pi) for _ in range(self._kernel_size)]
        return w, b
