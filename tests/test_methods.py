import awkward as ak
import numpy as np
import pytest
from numpy.random import default_rng
from scipy.stats import rankdata
from sklearn.preprocessing import LabelEncoder, normalize

from nessie.dataloader import (
    load_sequence_labeling_dataset,
    load_text_classification_tsv,
)
from nessie.detectors import (
    BordaCount,
    ClassificationEntropy,
    ClassificationUncertainty,
    ConfidentLearning,
    Detector,
    DropoutUncertainty,
    ItemResponseTheoryFlagger,
    MajorityLabelBaseline,
    MajorityLabelPerSurfaceFormBaseline,
)
from tests.fixtures import (
    PATH_EXAMPLE_DATA_SPAN,
    PATH_EXAMPLE_DATA_TEXT,
    PATH_EXAMPLE_DATA_TOKEN,
    generate_random_pos_tagging_dataset,
    generate_random_text_classification_dataset,
    get_random_ensemble_predictions,
    get_random_probabilities,
    get_random_repeated_probabilities,
)

# Smoke tests

NUM_INSTANCES = 100
NUM_LABELS = 4
NUM_MODELS = 3
T = 10


@pytest.fixture
def majority_label_baseline_fixture() -> MajorityLabelBaseline:
    return MajorityLabelBaseline()


@pytest.fixture
def majority_label_per_surface_form_baseline_fixture() -> MajorityLabelPerSurfaceFormBaseline:
    return MajorityLabelPerSurfaceFormBaseline()


@pytest.fixture
def classification_entropy_fixture() -> ClassificationEntropy:
    return ClassificationEntropy()


@pytest.fixture
def classification_uncertainty_fixture() -> ClassificationUncertainty:
    return ClassificationUncertainty()


@pytest.fixture
def confident_learning_fixture() -> ConfidentLearning:
    return ConfidentLearning()


@pytest.fixture
def dropout_uncertainty_fixture() -> DropoutUncertainty:
    return DropoutUncertainty()


@pytest.fixture
def irt_fixture() -> ItemResponseTheoryFlagger:
    return ItemResponseTheoryFlagger(num_iters=5)


@pytest.mark.parametrize(
    "detector_fixture",
    [
        "majority_label_baseline_fixture",
        "classification_entropy_fixture",
        "classification_uncertainty_fixture",
        "confident_learning_fixture",
        "dropout_uncertainty_fixture",
        "irt_fixture",
    ],
)
def test_detectors_for_text_classification(detector_fixture, request):
    detector: Detector = request.getfixturevalue(detector_fixture)
    ds = generate_random_text_classification_dataset(NUM_INSTANCES, NUM_LABELS)

    probabilities = get_random_probabilities(ds.num_instances, len(ds.tagset_noisy))
    repeated_probabilities = get_random_repeated_probabilities(ds.num_instances, len(ds.tagset_noisy), T)
    ensemble_predictions = get_random_ensemble_predictions(ds.num_instances, ds.tagset_noisy, NUM_MODELS)
    le = LabelEncoder().fit(ds.noisy_labels)

    params = {
        "texts": ds.texts,
        "labels": ds.noisy_labels,
        "probabilities": probabilities,
        "repeated_probabilities": repeated_probabilities,
        "ensemble_predictions": ensemble_predictions,
        "le": le,
    }

    detector.score(**params)


@pytest.mark.parametrize(
    "detector_fixture",
    [
        "majority_label_per_surface_form_baseline_fixture",
        "classification_entropy_fixture",
        "classification_uncertainty_fixture",
        "confident_learning_fixture",
        "dropout_uncertainty_fixture",
        "irt_fixture",
    ],
)
def test_detectors_for_text_classification_flat(detector_fixture, request):
    detector: Detector = request.getfixturevalue(detector_fixture)
    ds = generate_random_pos_tagging_dataset(NUM_INSTANCES, NUM_LABELS)

    probabilities_flat = get_random_probabilities(ds.num_instances, len(ds.tagset_noisy))
    repeated_probabilities_flat = get_random_repeated_probabilities(ds.num_instances, len(ds.tagset_noisy), T)
    ensemble_predictions = get_random_ensemble_predictions(ds.num_instances, ds.tagset_noisy, NUM_MODELS)
    le = LabelEncoder().fit(ak.flatten(ds.noisy_labels))

    params = {
        "texts": ak.flatten(ds.sentences),
        "labels": ak.flatten(ds.noisy_labels),
        "probabilities": probabilities_flat,
        "repeated_probabilities": repeated_probabilities_flat,
        "ensemble_predictions": ensemble_predictions,
        "le": le,
    }

    detector.score(**params)


@pytest.mark.parametrize(
    "detector_fixture",
    [
        "majority_label_per_surface_form_baseline_fixture",
        "classification_entropy_fixture",
        "classification_uncertainty_fixture",
        "confident_learning_fixture",
        "dropout_uncertainty_fixture",
        "irt_fixture",
    ],
)
def test_detectors_for_span_labeling_flat(detector_fixture, request):
    pass


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

    detector = ClassificationEntropy()
    scores = detector.score(probabilities)

    assert np.allclose(scores, expected)


def test_classification_uncertainty():
    n = 100
    k = 4

    le = LabelEncoder()
    le.classes_ = np.array(["A", "B", "C", "D"], dtype=object)

    probabilities = get_random_probabilities(n, k)
    encoded_labels = np.random.randint(0, k, n)
    labels = le.inverse_transform(encoded_labels)
    expected_scores = 1 - np.array([probabilities[i, encoded_labels[i]] for i in range(n)])

    detector = ClassificationUncertainty()
    scores = detector.score(labels, probabilities, le)

    assert np.array_equal(scores, expected_scores)
