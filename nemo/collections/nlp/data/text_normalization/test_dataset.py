# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
from typing import DefaultDict, List

from nemo.collections.nlp.data.text_normalization import constants
from nemo.collections.nlp.data.text_normalization.utils import (
    basic_tokenize,
    normalize_str,
    read_data_file,
    remove_puncts,
)
from nemo.utils.decorators.experimental import experimental

__all__ = ['TextNormalizationTestDataset']

# Test Dataset
@experimental
class TextNormalizationTestDataset:
    """
    Creates dataset to use to do end-to-end inference

    Args:
        input_file: path to the raw data file (e.g., train.tsv). For more info about the data format, refer to the `text_normalization doc <https://github.com/NVIDIA/NeMo/blob/main/docs/source/nlp/text_normalization.rst>`.
        mode: should be one of the values ['tn', 'itn', 'joint'].  `tn` mode is for TN only. `itn` mode is for ITN only. `joint` is for training a system that can do both TN and ITN at the same time.
        lang: Language of the dataset
    """

    def __init__(self, input_file: str, mode: str, lang: str):
        self.lang = lang
        insts = read_data_file(input_file)

        # Build inputs and targets
        self.directions, self.inputs, self.targets, self.classes, self.nb_spans, self.span_starts, self.span_ends = (
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        )
        for (classes, w_words, s_words) in insts:
            # Extract words that are not punctuations
            (
                processed_w_words,
                processed_s_words,
                processed_classes_tn,
                processed_classes_itn,
                processed_nb_spans_tn,
                processed_nb_spans_itn,
                w_span_starts,
                w_span_ends,
                processed_s_span_starts,
                processed_s_span_ends,
            ) = ([], [], [], [], 0, 0, [], [], [], [])
            w_word_idx = 0
            s_word_idx = 0
            for cls, w_word, s_word in zip(classes, w_words, s_words):
                w_span_starts.append(w_word_idx)
                w_word_idx += len(basic_tokenize(w_word, lang=self.lang))
                w_span_ends.append(w_word_idx)
                processed_nb_spans_tn += 1
                if s_word == constants.SIL_WORD:
                    processed_classes_tn.append(constants.PUNCT_TAG)
                    continue
                if s_word == constants.SELF_WORD:
                    processed_s_words.append(w_word)
                if not s_word in constants.SPECIAL_WORDS:
                    processed_s_words.append(s_word)
                processed_nb_spans_itn += 1
                processed_classes_tn.append(cls)
                processed_classes_itn.append(cls)
                processed_s_span_starts.append(s_word_idx)
                s_word_idx += len(basic_tokenize(processed_s_words[-1], lang=self.lang))
                processed_s_span_ends.append(s_word_idx)
                processed_w_words.append(w_word)
            # Create examples
            for direction in constants.INST_DIRECTIONS:
                if direction == constants.INST_BACKWARD:
                    if mode == constants.TN_MODE:
                        continue
                    input_words = processed_s_words
                    output_words = processed_w_words
                    self.span_starts.append(processed_s_span_starts)
                    self.span_ends.append(processed_s_span_ends)
                    self.classes.append(processed_classes_itn)
                    self.nb_spans.append(processed_nb_spans_itn)
                if direction == constants.INST_FORWARD:
                    if mode == constants.ITN_MODE:
                        continue
                    input_words = w_words
                    output_words = processed_s_words
                    self.span_starts.append(w_span_starts)
                    self.span_ends.append(w_span_ends)
                    self.classes.append(processed_classes_tn)
                    self.nb_spans.append(processed_nb_spans_tn)
                # Basic tokenization
                input_words = basic_tokenize(' '.join(input_words), lang)
                # Update self.directions, self.inputs, self.targets
                self.directions.append(direction)
                self.inputs.append(' '.join(input_words))
                self.targets.append(
                    output_words
                )  # is list of lists where inner list contains target tokens (not words)
        self.examples = list(
            zip(
                self.directions,
                self.inputs,
                self.targets,
                self.classes,
                self.nb_spans,
                self.span_starts,
                self.span_ends,
            )
        )

    def __getitem__(self, idx):
        return self.examples[idx]

    def __len__(self):
        return len(self.inputs)

    @staticmethod
    def is_same(pred: str, target: str, inst_dir: str, lang: str):
        """
        Function for checking whether the predicted string can be considered
        the same as the target string

        Args:
            pred: Predicted string
            target: Target string
            inst_dir: Direction of the instance (i.e., INST_BACKWARD or INST_FORWARD).
            lang: Language
        Return: an int value (0/1) indicating whether pred and target are the same.
        """
        if inst_dir == constants.INST_BACKWARD:
            pred = remove_puncts(pred)
            target = remove_puncts(target)
        pred = normalize_str(pred, lang)
        target = normalize_str(target, lang)
        return int(pred == target)

    @staticmethod
    def compute_sent_accuracy(preds: List[str], targets: List[str], inst_directions: List[str], lang: str):
        """
        Compute the sentence accuracy metric.

        Args:
            preds: List of predicted strings.
            targets: List of target strings.
            inst_directions: A list of str where each str indicates the direction of the corresponding instance (i.e., INST_BACKWARD or INST_FORWARD).
            lang: Language
        Return: the sentence accuracy score
        """
        assert len(preds) == len(targets)
        if len(targets) == 0:
            return 'NA'
        # Sentence Accuracy
        correct_count = 0
        for inst_dir, pred, target in zip(inst_directions, preds, targets):
            correct_count += TextNormalizationTestDataset.is_same(pred, target, inst_dir, lang)
        sent_accuracy = correct_count / len(targets)

        return sent_accuracy

    @staticmethod
    def compute_class_accuracy(
        inputs: List[List[str]],
        targets: List[List[str]],
        tag_preds: List[List[str]],
        inst_directions: List[str],
        output_spans: List[List[str]],
        classes: List[List[str]],
        nb_spans: List[int],
        span_starts: List[List[int]],
        span_ends: List[List[int]],
        lang: str,
    ) -> dict:
        """
        Compute the class based accuracy metric. This uses model's predicted tags.

        Args:
            inputs: List of lists where inner list contains words of input text
            targets: List of lists where inner list contains target strings grouped by class boundary
            tag_preds: List of lists where inner list contains predicted tags for each of the input words
            inst_directions: A list of str where each str indicates the direction of the corresponding instance (i.e., INST_BACKWARD or INST_FORWARD).
            output_spans: A list of lists where each inner list contains the decoded spans for the corresponding input sentence
            classes: A list of lists where inner list contains the class for each semiotic token in input sentence
            nb_spans: A list that contains the number of tokens in the input
            span_starts: A list of lists where inner list contains the start word index of the current token
            span_ends: A list of lists where inner list contains the end word index of the current token
            lang: Language
        Return: the class accuracy scores as dict
        """

        if len(targets) == 0:
            return 'NA'

        class2stats, class2correct = defaultdict(int), defaultdict(int)
        for ix, (sent, tags) in enumerate(zip(inputs, tag_preds)):
            cur_words = [[] for _ in range(nb_spans[ix])]
            jx, span_idx = 0, 0
            cur_spans = output_spans[ix]
            class_idx = 0
            if classes[ix]:
                class2stats[classes[ix][class_idx]] += 1
            while jx < len(sent):
                tag, word = tags[jx], sent[jx]
                while jx >= span_ends[ix][class_idx]:
                    class_idx += 1
                    class2stats[classes[ix][class_idx]] += 1
                if constants.SAME_TAG in tag:
                    cur_words[class_idx].append(word)
                    jx += 1
                elif constants.PUNCT_TAG in tag:
                    cur_words[class_idx].append(word)
                    jx += 1
                else:
                    jx += 1
                    tmp = cur_spans[span_idx]
                    cur_words[class_idx].append(tmp)
                    span_idx += 1
                    while jx < len(sent) and tags[jx] == constants.I_PREFIX + constants.TRANSFORM_TAG:
                        while jx >= span_ends[ix][class_idx]:
                            class_idx += 1
                            class2stats[classes[ix][class_idx]] += 1
                            cur_words[class_idx].append(tmp)
                        jx += 1

            target_token_idx = 0
            for class_idx in range(nb_spans[ix]):
                if classes[ix][class_idx] == constants.PUNCT_TAG:
                    continue
                correct = TextNormalizationTestDataset.is_same(
                    " ".join(cur_words[class_idx]), targets[ix][target_token_idx], inst_directions[ix], lang
                )
                class2correct[classes[ix][class_idx]] += correct
                target_token_idx += 1

        for key in class2stats:
            class2stats[key] = (class2correct[key] / class2stats[key], class2correct[key], class2stats[key])

        return class2stats
