import awkward as ak
import numpy as np
import pytest
from numpy.random import default_rng
from scipy.stats import rankdata
from sklearn.preprocessing import normalize

from nessie.dataloader import (
    load_sequence_labeling_dataset,
    load_text_classification_tsv,
)
from nessie.detectors import (
    BordaCount,
    ClassificationEntropy,
    Detector,
    MajorityLabelBaseline,
    MajorityLabelPerSurfaceFormBaseline,
)
from tests.fixtures import (
    PATH_EXAMPLE_DATA_SPAN,
    PATH_EXAMPLE_DATA_TEXT,
    PATH_EXAMPLE_DATA_TOKEN,
)

# Smoke tests


@pytest.fixture
def majority_label_baseline_fixture() -> MajorityLabelBaseline:
    return MajorityLabelBaseline()


@pytest.fixture
def majority_label_per_surface_form_baseline_fixture() -> MajorityLabelPerSurfaceFormBaseline:
    return MajorityLabelPerSurfaceFormBaseline()


@pytest.fixture
def classification_entropy_fixture() -> ClassificationEntropy:
    return ClassificationEntropy()


@pytest.mark.parametrize(
    "detector_fixture",
    ["majority_label_baseline_fixture", "classification_entropy_fixture"],
)
def test_detectors_for_text_classification(detector_fixture, request):
    detector: Detector = request.getfixturevalue(detector_fixture)
    ds = load_text_classification_tsv(PATH_EXAMPLE_DATA_TEXT)

    num_instances = ds.num_instances
    num_labels = len(ds.tagset_noisy)

    rng = default_rng()
    probabilities = rng.random((num_instances, num_labels))
    probabilities = normalize(probabilities, norm="l1", axis=1)

    params = {"texts": ds.texts, "labels": ds.noisy_labels, "probabilities": probabilities}

    detector.score(**params)


@pytest.mark.parametrize(
    "detector_fixture",
    [
        "majority_label_per_surface_form_baseline_fixture",
    ],
)
def test_detectors_for_text_classification_flat(detector_fixture, request):
    detector: Detector = request.getfixturevalue(detector_fixture)
    ds = load_sequence_labeling_dataset(PATH_EXAMPLE_DATA_TOKEN)

    num_instances = ds.num_instances
    num_labels = len(ds.tagset_noisy)

    rng = default_rng()
    flattened_probabilities = rng.random((num_instances, num_labels))
    flattened_probabilities = normalize(flattened_probabilities, norm="l1", axis=1)

    params = {
        "texts": ak.flatten(ds.sentences),
        "labels": ak.flatten(ds.noisy_labels),
        "probabilities": flattened_probabilities,
    }

    detector.score(**params)


@pytest.mark.parametrize(
    "detector_fixture",
    [
        "majority_label_per_surface_form_baseline_fixture",
    ],
)
def test_detectors_for_span_labeling_flat(detector_fixture, request):
    detector: Detector = request.getfixturevalue(detector_fixture)
    ds = load_sequence_labeling_dataset(PATH_EXAMPLE_DATA_SPAN)

    params = {"texts": ak.flatten(ds.sentences), "labels": ak.flatten(ds.noisy_labels)}

    detector.score(**params)


# Method specific tests


def test_majority_label_baseline():
    detector = MajorityLabelBaseline()

    texts = [
        "I like cookies.",
        "I like reindeer.",
        "He likes sunsets and long strolls on the beach.",
        "He does not like Mondays.",
    ]

    labels = ["pos", "pos", "pos", "neg"]

    flags = detector.score(texts, labels)

    assert list(flags) == [False, False, False, True]


def test_majority_label_per_surface_form_baseline():
    detector = MajorityLabelPerSurfaceFormBaseline()

    sentences = [
        ["Obama", "Harvard"],
        ["Harvard"],
        ["Harvard", "Boston"],
    ]

    labels = [
        ["PER", "LOC"],
        ["LOC"],
        ["MISC", "LOC"],
    ]

    sentences = ak.flatten(ak.Array(sentences))
    labels = ak.flatten(ak.Array(labels))

    flags = detector.score(sentences, labels)

    assert len(sentences) == len(labels) == len(flags)
    assert list(flags) == [False, False, False, True, False]


def test_borda_count():
    votes = np.array(
        [
            [4, 3, 2, 1],
            [4, 3, 2, 1],
            [1, 4, 3, 2],
        ]
    )

    method = BordaCount()
    scores = method.score(votes)

    # We invert scores so that ranks are computed from largest to lowest
    actual_ranks = rankdata(-scores, method="ordinal")

    assert np.array_equal(actual_ranks, np.array([2, 1, 3, 4]))


@pytest.mark.parametrize(
    "proba,expected", [([[0.1, 0.85, 0.05], [0.6, 0.3, 0.1], [0.39, 0.61, 0.0]], [0.51818621, 0.89794572, 0.66874809])]
)
def test_classification_entropy(proba, expected):
    # https://modal-python.readthedocs.io/en/latest/content/query_strategies/uncertainty_sampling.html

    probabilities = np.array(proba)

    algo = ClassificationEntropy()
    scores = algo.score(probabilities)

    assert np.allclose(scores, expected)