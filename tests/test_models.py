from itertools import combinations

import awkward as ak
import numpy as np
import pytest

from nessie.dataloader import (
    SequenceLabelingDataset,
    TextClassificationDataset,
    load_sequence_labeling_dataset,
    load_text_classification_tsv,
)
from nessie.models import SequenceTagger, TextClassifier
from nessie.models.featurizer import CachedSentenceTransformer, TfIdfSentenceEmbedder
from nessie.models.tagging import (
    CrfSequenceTagger,
    FlairSequenceTagger,
    MaxEntSequenceTagger,
    TransformerSequenceTagger,
)
from nessie.models.text import (
    FastTextTextClassifier,
    FlairTextClassifier,
    LgbmTextClassifier,
    MaxEntTextClassifier,
    TransformerTextClassifier,
)
from tests.fixtures import PATH_EXAMPLE_DATA_TEXT, PATH_EXAMPLE_DATA_TOKEN

BERT_BASE = "google/bert_uncased_L-2_H-128_A-2"
SBERT_MODEL_NAME = "all-MiniLM-L6-v2"

# Sequence Tagger


@pytest.fixture
def crf_sequence_tagger_fixture():
    return CrfSequenceTagger()


@pytest.fixture
def flair_sequence_tagger_fixture():
    max_epochs = 1
    batch_size = 32
    return FlairSequenceTagger(max_epochs=max_epochs, batch_size=batch_size)


@pytest.fixture
def maxent_sequence_tagger_fixture():
    return MaxEntSequenceTagger(max_iter=100)


@pytest.fixture
def transformer_sequence_tagger_fixture():
    max_epochs = 1
    batch_size = 16
    return TransformerSequenceTagger(max_epochs=max_epochs, batch_size=batch_size, model_name=BERT_BASE)


# Text classifier


@pytest.fixture
def fasttext_text_classifier_fixture():
    return FastTextTextClassifier()


@pytest.fixture
def flair_text_classifier_fixture():
    max_epochs = 2
    batch_size = 32
    return FlairTextClassifier(max_epochs=max_epochs, batch_size=batch_size)


@pytest.fixture
def lightgbm_tfidf_text_classifier_fixture():
    return LgbmTextClassifier(TfIdfSentenceEmbedder())


@pytest.fixture
def lightgbm_sbert_text_classifier_fixture():
    return LgbmTextClassifier(CachedSentenceTransformer(SBERT_MODEL_NAME))


@pytest.fixture
def maxent_tfidf_text_classifier_fixture():
    return MaxEntTextClassifier(TfIdfSentenceEmbedder(), max_iter=100)


@pytest.fixture
def maxent_sbert_text_classifier_fixture():
    return MaxEntTextClassifier(CachedSentenceTransformer(SBERT_MODEL_NAME), max_iter=100)


@pytest.fixture
def transformer_text_classifier_fixture():
    max_epochs = 1
    batch_size = 16
    return TransformerTextClassifier(max_epochs=max_epochs, batch_size=batch_size, model_name=BERT_BASE)


# Smoke tests


@pytest.mark.parametrize(
    "model_fixture",
    [
        "crf_sequence_tagger_fixture",
        "flair_sequence_tagger_fixture",
        "maxent_sequence_tagger_fixture",
        "transformer_sequence_tagger_fixture",
    ],
)
def test_sequence_classification_models(model_fixture: str, request):
    model: SequenceTagger = request.getfixturevalue(model_fixture)

    ds = get_sequence_tagging_data()

    N = ds.num_sentences
    k = len(ds.tagset_noisy)

    model.fit(ds.sentences, ds.noisy_labels)

    predictions = model.predict(ds.sentences)
    scores = model.score(ds.sentences)
    probs = model.predict_proba(ds.sentences)

    assert type(predictions) == ak.Array
    assert type(scores) == ak.Array
    assert type(probs) == ak.Array

    assert len(predictions) == N
    assert len(scores) == N
    assert len(probs) == N
    assert model.label_encoder()
    assert set(model.label_encoder().classes_) == ds.tagset_noisy

    sizes_tokens = ak.num(ds.sentences)
    sizes_labels = ak.num(ds.noisy_labels)
    sizes_predictions = ak.num(predictions)
    sizes_scores = ak.num(scores)
    sizes_probs = ak.num(probs)

    # Check that the sizes (the ragged parts) of all the things match
    for pair in combinations([sizes_tokens, sizes_labels, sizes_predictions, sizes_scores, sizes_probs], 2):
        assert np.array_equal(pair[0], pair[1])

    scores_flattened = ak.flatten(scores).to_numpy()
    probs_flattened = ak.flatten(probs).to_numpy()

    assert scores_flattened.shape == (np.sum(sizes_tokens),)
    assert probs_flattened.shape == (np.sum(sizes_tokens), k)

    assert np.issubdtype(scores_flattened.dtype, np.floating)
    assert np.issubdtype(probs_flattened.dtype, np.floating)

    # Check that probs sum up to 1
    assert np.allclose(np.sum(probs_flattened, axis=1), np.ones_like(scores_flattened))


@pytest.mark.parametrize(
    "model_fixture",
    [
        "fasttext_text_classifier_fixture",
        "flair_text_classifier_fixture",
        "lightgbm_tfidf_text_classifier_fixture",
        "lightgbm_sbert_text_classifier_fixture",
        "maxent_tfidf_text_classifier_fixture",
        "maxent_sbert_text_classifier_fixture",
        "transformer_text_classifier_fixture",
    ],
)
def test_text_classification_models(model_fixture: str, request):
    model: TextClassifier = request.getfixturevalue(model_fixture)

    ds = get_text_classification_data()
    unique_labels = ds.tagset_noisy

    N = len(ds.texts)
    k = len(unique_labels)

    model.fit(ds.texts, ds.noisy_labels)

    predictions = model.predict(ds.texts)
    scores = model.score(ds.texts)
    probs = model.predict_proba(ds.texts)

    assert type(predictions) == np.ndarray
    assert type(scores) == np.ndarray
    assert type(probs) == np.ndarray

    assert len(predictions) == N
    assert np.array(scores).shape == (N,)
    assert np.array(probs).shape == (N, k)
    assert model.label_encoder()
    assert len(model.label_encoder().classes_) == k
    assert set(model.label_encoder().classes_) == unique_labels

    assert np.issubdtype(scores.dtype, np.floating)
    assert np.issubdtype(probs.dtype, np.floating)

    # Check that probs sum up to 1
    assert np.allclose(np.sum(probs, axis=1), np.ones_like(scores))


def get_sequence_tagging_data() -> SequenceLabelingDataset:
    return load_sequence_labeling_dataset(PATH_EXAMPLE_DATA_TOKEN).subset(100)


def get_text_classification_data() -> TextClassificationDataset:
    return load_text_classification_tsv(PATH_EXAMPLE_DATA_TEXT).subset(100)
