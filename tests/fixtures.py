from pathlib import Path

import numpy as np
import numpy.typing as npt
from numpy.random import default_rng
from sklearn.preprocessing import normalize

PATH_ROOT: Path = Path(__file__).resolve().parents[1]

# Example data
PATH_EXAMPLE_DATA: Path = PATH_ROOT / "example_data"
PATH_EXAMPLE_DATA_TEXT: Path = PATH_EXAMPLE_DATA / "easy_text.tsv"
PATH_EXAMPLE_DATA_TOKEN: Path = PATH_EXAMPLE_DATA / "easy_token.conll"
PATH_EXAMPLE_DATA_SPAN: Path = PATH_EXAMPLE_DATA / "easy_span.conll"


def get_random_probabilities(num_instances: int, num_labels: int) -> npt.NDArray[float]:
    rng = default_rng()
    probabilities = rng.random((num_instances, num_labels))
    probabilities = normalize(probabilities, norm="l1", axis=1)

    return probabilities


def get_repeated_probabilities(num_instances: int, num_labels: int, T: int) -> npt.NDArray[float]:
    result = []

    for _ in range(T):
        probabilities = get_random_probabilities(num_instances, num_labels)
        probabilities = normalize(probabilities, norm="l1", axis=1)
        result.append(probabilities)

    result = np.asarray(result).swapaxes(0, 1)

    assert result.shape == (num_instances, T, num_labels)

    return result
