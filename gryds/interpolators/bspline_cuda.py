#! /usr/bin/env python
#
# Resample images on a new Grid instance using B-spline interplation


from __future__ import division, print_function, absolute_import

import numpy as np
import cupyx.scipy.ndimage as nd
import cupy as cp
from ..config import DTYPE
from .grid import Grid
from .base import Interpolator


class BSplineInterpolatorCUDA(Interpolator):
    """An interpolator for an image that can resample an image on a new grid,
    or transform an image.

    Attributes:
        self.image (np.ndarray): The wrapped ND image.
        self.grid (Grid): The image's default sampling grid.
        self.default_mode (str): Determines how edges are treated.
        self.default_order (int): B-Spline order. Currently, only 0 and 1 are
            supported.
        self.default_cval (numeric): Constant value for mode='constant'.
    """

    def __init__(self, image, mode='constant', order=1, cval=0):
        """
        Args:
            image (np.array): An image array.
            order (int): The order of the B-spline. Default is 1. Use 0 for
                binary images. Use 1 for normal linear interpolation.
            mode (str): How edges of image domain should be treated when
                transformed of 'constant', 'nearest', 'mirror', 'reflect',
                'wrap'. Default is 'constant'. See https://docs.scipy.org/doc/
                scipy-0.14.0/reference/generated/
                scipy.ndimage.interpolation.map_coordinates.html for more
                information about modes.
            cval (numeric): Constant value for mode='constant'.
        """
        super(BSplineInterpolatorCUDA, self).__init__(
            image
        )
        self.default_mode = mode
        self.default_order = order
        self.default_cval = cval

    def sample(self, points, mode=None, order=None, cval=None):
        """
        Samples the image at given points.

        Args:
            points (np.array): An N x ndims array of points.
            order (int): The order of the B-spline. Default is 3. Use 0 for
                binary images. Use 1 for normal linear interpolation.
            mode (str): How edges of image domain should be treated when
                transformed of 'constant', 'nearest', 'mirror', 'reflect',
                'wrap'. Default is 'constant'. See https://docs.scipy.org/doc/
                scipy-0.14.0/reference/generated/
                scipy.ndimage.interpolation.map_coordinates.html for more
                information about modes.
            cval (numeric): Constant value for mode='constant'
        Returns:
            np.array: N-shaped array of intensities at the points.
        """
        new_mode = mode if mode else self.default_mode
        new_order = order if order else self.default_order
        new_cval = cval if cval else self.default_cval

        # Reshape points for the cupy map_coordinates function to
        # receive coordinates in the expected shape
        points = np.transpose(points.reshape(self.image.ndim, -1))
        sample_gpu = nd.map_coordinates(input=cp.array(self.image),
                                        coordinates=cp.array(points),
                                        mode=new_mode,
                                        order=new_order,
                                        cval=new_cval)

        # Convert back to CPU array and reshape to original shape
        sample_cpu = cp.asnumpy(sample_gpu)
        sample = sample_cpu.reshape(self.image.shape)
        return np.array(sample.astype(DTYPE))

    def resample(self, grid, mode=None, order=None, cval=None):
        """
        Reamples the image at a given grid.

        Args:
            grid (Grid): The new grid.
            order (int): The order of the B-spline. Default is 3. Use 0 for
                binary images. Use 1 for normal linear interpolation.
            mode (str): How edges of image domain should be treated when
                transformed of 'constant', 'nearest', 'mirror', 'reflect',
                'wrap'. Default is 'constant'. See https://docs.scipy.org/doc/
                scipy-0.14.0/reference/generated/
                scipy.ndimage.interpolation.map_coordinates.html for more
                information about modes.
            cval (numeric): Constant value for mode='constant'
        Returns:
            np.array: The resampled image at the new grid.
        """
        rescaled_grid = grid.scaled_to(self.image.shape)
        new_image = self.sample(rescaled_grid.grid,
                                mode=mode,
                                order=order,
                                cval=cval)
        return new_image.astype(DTYPE)

    def transform(self, *transforms, **kwargs):
        """
        Transforms the image by transforming the original image's grid and
        resampling the image at the transformed grid.

        Args:
            *transforms (list): A list of Transform objects.
            order (int): The order of the B-spline. Default is 3. Use 0 for
                binary images. Use 1 for normal linear interpolation.
            mode (str): How edges of image domain should be treated when
                transformed of 'constant', 'nearest', 'mirror', 'reflect',
                'wrap'. Default is 'constant'. See https://docs.scipy.org/doc/
                scipy-0.14.0/reference/generated/
                scipy.ndimage.interpolation.map_coordinates.html for more
                information about modes.
            cval (numeric): Constant value for mode='constant'
        Returns:
            np.array: The transformed image.
        """
        mode = kwargs['mode'] if 'mode' in kwargs else None
        order = kwargs['order'] if 'order' in kwargs else None
        cval = kwargs['cval'] if 'cval' in kwargs else None

        transformed_grid = self.grid.transform(*transforms)
        new_grid = self.resample(transformed_grid,
                                 mode=mode, order=order, cval=cval)
        return new_grid.astype(DTYPE)
