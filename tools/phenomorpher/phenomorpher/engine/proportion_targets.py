"""Human-relative proposed dimensions; never approves fitting or asset changes."""
import numpy as np
from .measurement_common import require


def transfer(donor_dimension, donor_height, race_fraction, human_fraction, target_height):
    values = (donor_dimension, donor_height, race_fraction, human_fraction, target_height)
    require(all(np.isfinite(v) and v > 0 for v in values), 'Positive finite ratio inputs required')
    return donor_dimension / donor_height * race_fraction / human_fraction * target_height
